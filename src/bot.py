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

class RedditBot:
    def __init__(self, llm_provider: str = "ollama", llm_model: Optional[str] = None):
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
            llm_handler=handler_class(self.logger, model)
        )
        self.running = False
        self.post_queue = asyncio.Queue()
        self.processing_queue = asyncio.Queue()
        self._scan_lock = asyncio.Lock()  # Add lock for scanning
        
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
            self.comment_processor()
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
    
    args = parser.parse_args()
    
    bot = RedditBot(
        llm_provider=args.llm_provider,
        llm_model=args.llm_model
    )
    bot.run()

if __name__ == "__main__":
    main() 