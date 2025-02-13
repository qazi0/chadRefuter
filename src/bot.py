import time
import signal
import sys
import schedule
import threading
from queue import Queue
from config import Config
from logger import BotLogger
from reddit_api import RedditAPI
from post_handler import PostHandler, PostCache
import asyncio
from typing import Optional, Type
import argparse
from llm_handler import (
    LLMHandler,
    OllamaHandler,
    OpenAIHandler,
    AnthropicHandler,
    HuggingFaceHandler,
    GeminiHandler
)
import os
import random

class RedditBot:
    def __init__(self, llm_provider: str = "ollama", llm_model: Optional[str] = None, system_prompt_path: str = "src/system_prompt.md"):
        self.logger = BotLogger()
        self.config = Config()
        
        # LLM provider mapping
        self.llm_providers = {
            "ollama": (OllamaHandler, "llama3.1:8b"),
            "openai": (OpenAIHandler, "gpt-3.5-turbo"),
            "anthropic": (AnthropicHandler, "claude-3-sonnet-20240229"),
            "huggingface": (HuggingFaceHandler, "meta-llama/Llama-2-7b-chat-hf"),
            "gemini": (GeminiHandler, "gemini-2.0-flash")
        }
        
        # Initialize the chosen LLM handler
        handler_class, default_model = self.llm_providers[llm_provider]
        model = llm_model or default_model
        
        try:
            self.config.validate()
        except ValueError as e:
            self.logger.error(str(e))
            sys.exit(1)
            
        self.reddit_api = RedditAPI(self.config, self.logger)
        self.post_handler = PostHandler(
            self.reddit_api, 
            self.logger,
            llm_handler=handler_class(self.logger, system_prompt_path, model)
        )
        self.running = False
        self.post_queue = asyncio.Queue()
        self.processing_queue = asyncio.Queue()
        self._scan_lock = asyncio.Lock()
        self.reply_queue = asyncio.Queue()
        self.max_conversation_depth = 5
        self.reply_delay_range = (30, 120)
        
        # Track if this is first run
        self.has_previous_comments = self._check_previous_comments()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        # Add database status logging on startup
        last_posts = self.post_handler.db.fetch_last_n_posts(5)
        if last_posts:
            self.logger.info(
                f"Found {len(last_posts)} previously processed posts in database",
                f"Last processed post: {last_posts[0][1][:50]}..."
            )
    
    def _check_previous_comments(self) -> bool:
        """Check if the bot has any previous comments"""
        try:
            comments = list(self.reddit_api.reddit.user.me().comments.new(limit=1))
            return len(comments) > 0
        except Exception as e:
            self.logger.error(f"Error checking previous comments: {str(e)}")
            return False
    
    async def scan_posts(self):
        """Scan for new posts and add them to the processing queue"""
        async with self._scan_lock:  # Ensure only one scan runs at a time
            try:
                self.logger.info("Scanning for new posts...")
                new_posts = self.post_handler.fetch_new_posts(limit=self.config.posts_fetch_limit)
                for post in new_posts:
                    await self.post_queue.put(post)
                if not new_posts:
                    self.logger.info("No new posts found in this scan")
            except Exception as e:
                self.logger.error(f"Error in post scanning: {str(e)}")
    
    async def initial_scan(self):
        """Perform initial scan of the latest posts"""
        self.logger.info(f"Performing initial scan of the latest {self.config.posts_fetch_limit} posts...")
        try:
            # Clear cache to ensure we process the latest posts
            self.post_handler.post_cache = PostCache(max_size=self.config.post_cache_size)
            await self.scan_posts()
        except Exception as e:
            self.logger.error(f"Error in initial scan: {str(e)}")
    
    async def scheduled_scan(self):
        """Periodic scan that runs on a schedule"""
        while self.running:
            await self.scan_posts()
            await asyncio.sleep(self.config.scan_interval)
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        self.logger.info("Shutdown signal received. Cleaning up...")
        self.running = False
    
    async def process_post_with_llm(self, post) -> Optional[str]:
        """Process a post through the LLM and handle the response"""
        try:
            response = await self.post_handler.process_post(post)
            if response:
                # If response generated, add to processing queue
                await self.processing_queue.put((post, response))
                self.logger.info(f"Generated response for post {post.id}, queued for commenting")
                return response
            return None
        except Exception as e:
            self.logger.error(f"Error processing post {post.id} with LLM: {str(e)}")
            return None

    async def comment_processor(self):
        """Process the comment queue while respecting rate limits"""
        while self.running:
            try:
                if not self.processing_queue.empty():
                    post, response = await self.processing_queue.get()
                    
                    # Post the comment (this method handles the delay internally)
                    comment_id = await self.reddit_api.post_comment(post.id, response)
                    
                    if comment_id:
                        self.has_previous_comments = True  # Set flag when first comment is made
                        self.logger.info(
                            f"Successfully posted comment on {post.id}",
                            f"Comment posted: {comment_id}"
                        )
                    
                    self.processing_queue.task_done()
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in comment processing: {str(e)}")
                await asyncio.sleep(5)

    async def process_queue(self):
        """Process posts from the queue asynchronously"""
        while self.running:
            try:
                if not self.post_queue.empty():
                    post = await self.post_queue.get()
                    self.logger.debug(f"Processing post: {post.id}")
                    
                    await self.process_post_with_llm(post)
                    self.post_queue.task_done()
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                await asyncio.sleep(5)

    async def scan_comment_replies(self):
        """Scan for new replies to the bot's comments"""
        try:
            self.logger.info("Scanning for new comment replies...")
            
            # Get bot's recent comments
            async for comment in self.reddit_api.get_bot_comments():
                # Get replies to this comment
                replies = await self.reddit_api.get_comment_replies(comment.id)
                
                for reply in replies:
                    # Skip if it's our own reply or already processed
                    if (reply.author == self.config.username or 
                        self.post_handler.db.is_reply_processed(reply.id)):
                        continue
                    
                    # Get conversation depth
                    depth = self.post_handler.db.get_conversation_depth(comment.id) + 1
                    
                    # Skip if max depth reached
                    if depth > self.max_conversation_depth:
                        continue
                    
                    # Queue reply for processing
                    await self.reply_queue.put({
                        'parent_comment_id': comment.id,
                        'reply_id': reply.id,
                        'reply_text': reply.body,
                        'author': reply.author.name,
                        'depth': depth
                    })
                    
        except Exception as e:
            self.logger.error(f"Error scanning comment replies: {str(e)}")

    async def process_comment_replies(self):
        """Process queued comment replies"""
        while self.running:
            try:
                if not self.reply_queue.empty():
                    reply_data = await self.reply_queue.get()
                    
                    # Generate response using LLM
                    response = await self.post_handler.process_reply(
                        reply_data['reply_text'],
                        reply_data['depth']
                    )
                    
                    if response:
                        # Add random delay to seem more human-like
                        delay = random.randint(*self.reply_delay_range)
                        await asyncio.sleep(delay)
                        
                        # Post the reply
                        reply_comment_id = await self.reddit_api.post_reply(
                            reply_data['reply_id'],
                            response
                        )
                        
                        if reply_comment_id:
                            # Save to database
                            self.post_handler.db.save_comment_reply(
                                reply_data['parent_comment_id'],
                                reply_data['reply_id'],
                                reply_data['reply_text'],
                                reply_data['author'],
                                reply_data['depth'],
                                response
                            )
                            
                            self.logger.info(
                                f"Posted reply to comment {reply_data['reply_id']}",
                                f"Reply: {response[:100]}..."
                            )
                    
                    self.reply_queue.task_done()
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error processing comment reply: {str(e)}")
                await asyncio.sleep(5)

    async def scheduled_reply_scan(self):
        """Periodic scan for comment replies"""
        while self.running:
            # Only scan for replies if we have previous comments
            if self.has_previous_comments:
                await self.scan_comment_replies()
            else:
                # Check if we have any comments now
                self.has_previous_comments = self._check_previous_comments()
                if not self.has_previous_comments:
                    self.logger.debug("No previous comments found, skipping reply scan")
            
            await asyncio.sleep(300)  # 5 minutes

    async def run_async(self):
        """Async version of the main bot loop"""
        self.running = True
        self.logger.info("Bot started successfully")
        
        # Perform initial scan
        await self.initial_scan()
        
        # Process all queues concurrently
        await asyncio.gather(
            self.scheduled_scan(),
            self.process_queue(),
            self.comment_processor(),
            self.scheduled_reply_scan(),  # Add reply scanning
            self.process_comment_replies()  # Add reply processing
        )
        
        # Cleanup
        await self.post_handler.close()
        self.logger.info("Bot shutdown complete")

    def run(self):
        """Main entry point"""
        asyncio.run(self.run_async())

def main():
    parser = argparse.ArgumentParser(description="Reddit Bot with multiple LLM providers")
    parser.add_argument(
        "--llm-provider",
        choices=["ollama", "openai", "anthropic", "huggingface", "gemini"],
        default="ollama",
        help="Choose the LLM provider (default: ollama)"
    )
    parser.add_argument(
        "--llm-model",
        help="Specify the model for the chosen provider (optional)"
    )
    parser.add_argument(
        "--system-prompt",
        default="src/system_prompt.md",
        help="Path to system prompt file (default: src/system_prompt.md)"
    )
    
    args = parser.parse_args()
    
    # Validate system prompt file exists
    if not os.path.exists(args.system_prompt):
        print(f"Error: System prompt file not found at {args.system_prompt}")
        sys.exit(1)
    
    bot = RedditBot(
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        system_prompt_path=args.system_prompt
    )
    bot.run()

if __name__ == "__main__":
    main() 