import praw
from time import sleep
from prawcore.exceptions import PrawcoreException
import asyncio
import time
from typing import Optional

class RedditAPI:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.reddit = None
        self.initialize_reddit()
        self.comment_delay = 120  # Changed to 120 seconds (2 minutes) delay between comments
        self.last_comment_time = 0
        
    def initialize_reddit(self):
        """Initialize the Reddit API connection"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                username=self.config.username,
                password=self.config.password,
                user_agent=self.config.user_agent,
                check_for_async=False
            )
            self.logger.info(f"Successfully authenticated as {self.config.username}")
        except PrawcoreException as e:
            self.logger.error(f"Failed to initialize Reddit API: {str(e)}")
            raise
            
    def get_subreddit(self):
        """Get subreddit instance"""
        try:
            return self.reddit.subreddit(self.config.subreddit)
        except PrawcoreException as e:
            self.logger.error(f"Failed to get subreddit: {str(e)}")
            raise
            
    def handle_rate_limit(self, action):
        """Decorator to handle rate limiting"""
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return action(*args, **kwargs)
                except praw.exceptions.APIException as e:
                    if e.error_type == "RATELIMIT":
                        wait_time = 60  # Default wait time
                        self.logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                        sleep(wait_time)
                        continue
                    raise
        return wrapper 

    async def post_comment(self, post_id: str, text: str) -> Optional[str]:
        """Post a comment on Reddit with rate limiting"""
        try:
            # Calculate time to wait based on last comment
            current_time = time.time()
            time_since_last = current_time - self.last_comment_time
            
            if time_since_last < self.comment_delay:
                wait_time = self.comment_delay - time_since_last
                self.logger.info(
                    f"Rate limiting: Waiting {wait_time:.1f} seconds before posting comment",
                    f"Waiting {wait_time:.1f}s before next comment"
                )
                await asyncio.sleep(wait_time)

            submission = self.reddit.submission(id=post_id)
            comment = submission.reply(body=text)
            
            self.last_comment_time = time.time()
            self.logger.debug(f"Updated last comment time to: {self.last_comment_time}")
            return comment.id

        except Exception as e:
            self.logger.error(f"Error posting comment on {post_id}: {str(e)}")
            return None 

    async def get_bot_comments(self):
        """Get the bot's recent comments"""
        try:
            comments = list(self.reddit.user.me().comments.new(limit=100))
            for comment in comments:
                yield comment
        except Exception as e:
            self.logger.error(f"Error fetching bot comments: {str(e)}")

    async def get_comment_replies(self, comment_id: str):
        """Get replies to a specific comment"""
        try:
            comment = self.reddit.comment(comment_id)
            comment.refresh()  # Refresh to get the latest replies
            return list(comment.replies)  # Convert CommentForest to list
        except Exception as e:
            self.logger.error(f"Error fetching comment replies: {str(e)}")
            return []

    async def post_reply(self, parent_id: str, text: str) -> Optional[str]:
        """Post a reply to a comment"""
        try:
            # Calculate time to wait based on last comment
            current_time = time.time()
            time_since_last = current_time - self.last_comment_time
            
            if time_since_last < self.comment_delay:
                wait_time = self.comment_delay - time_since_last
                self.logger.info(
                    f"Rate limiting: Waiting {wait_time:.1f} seconds before posting reply",
                    f"Waiting {wait_time:.1f}s before next reply"
                )
                await asyncio.sleep(wait_time)

            comment = self.reddit.comment(parent_id)
            reply = comment.reply(body=text)
            
            self.last_comment_time = time.time()
            self.logger.debug(f"Updated last comment time to: {self.last_comment_time}")
            return reply.id

        except Exception as e:
            self.logger.error(f"Error posting reply to {parent_id}: {str(e)}")
            return None 