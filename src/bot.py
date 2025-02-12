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
from typing import Optional

class RedditBot:
    def __init__(self):
        self.logger = BotLogger()
        self.config = Config()
        
        try:
            self.config.validate()
        except ValueError as e:
            self.logger.error(str(e))
            sys.exit(1)
            
        self.reddit_api = RedditAPI(self.config, self.logger)
        self.post_handler = PostHandler(self.reddit_api, self.logger)
        self.running = False
        self.post_queue = Queue()
        
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
    
    def scan_posts(self):
        """Scan for new posts and add them to the processing queue"""
        try:
            self.logger.info("Scanning for new posts...")
            new_posts = self.post_handler.fetch_new_posts(limit=self.config.posts_fetch_limit)
            for post in new_posts:
                self.post_queue.put(post)
            if not new_posts:
                self.logger.info("No new posts found in this scan")
        except Exception as e:
            self.logger.error(f"Error in post scanning: {str(e)}")
    
    def initial_scan(self):
        """Perform initial scan of the latest posts"""
        self.logger.info(f"Performing initial scan of the latest {self.config.posts_fetch_limit} posts...")
        try:
            # Clear cache to ensure we process the latest posts
            self.post_handler.post_cache = PostCache(max_size=self.config.post_cache_size)
            self.scan_posts()
        except Exception as e:
            self.logger.error(f"Error in initial scan: {str(e)}")
    
    def run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        self.logger.info("Shutdown signal received. Cleaning up...")
        self.running = False
    
    async def process_post_with_llm(self, post) -> Optional[str]:
        """Process a post through the LLM and handle the response"""
        try:
            response = await self.post_handler.process_post(post)
            if response:
                self.logger.info(f"Successfully generated response for post {post.id}")
                return response
            return None
        except Exception as e:
            self.logger.error(f"Error processing post {post.id} with LLM: {str(e)}")
            return None

    async def process_queue(self):
        """Process posts from the queue asynchronously"""
        while self.running:
            try:
                if not self.post_queue.empty():
                    post = self.post_queue.get_nowait()
                    self.logger.debug(f"Processing post: {post.id}")
                    
                    response = await self.process_post_with_llm(post)
                    if response:
                        # Store or handle the response as needed
                        pass
                    
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
        self.initial_scan()
        
        # Schedule regular post scanning
        schedule.every(self.config.scan_interval).seconds.do(self.scan_posts)
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self.run_scheduler)
        scheduler_thread.start()
        
        # Process queue asynchronously
        await self.process_queue()
        
        # Cleanup
        scheduler_thread.join()
        await self.post_handler.close()
        self.logger.info("Bot shutdown complete")

    def run(self):
        """Main entry point"""
        asyncio.run(self.run_async())

if __name__ == "__main__":
    bot = RedditBot()
    bot.run() 