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
    
    def run(self):
        """Main bot loop"""
        self.running = True
        self.logger.info("Bot started successfully")
        
        # Perform initial scan
        self.initial_scan()
        
        # Schedule regular post scanning
        schedule.every(self.config.scan_interval).seconds.do(self.scan_posts)
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self.run_scheduler)
        scheduler_thread.start()
        
        while self.running:
            try:
                # Process posts from the queue
                if not self.post_queue.empty():
                    post = self.post_queue.get(timeout=1)
                    self.logger.debug(f"Processing post: {post.id}")
                    # Post processing will be implemented in the next stage
                    self.post_queue.task_done()
                else:
                    time.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                time.sleep(5)  # Wait before retrying
        
        # Clean up
        scheduler_thread.join()
        self.logger.info("Bot shutdown complete")

if __name__ == "__main__":
    bot = RedditBot()
    bot.run() 