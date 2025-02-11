import praw
from time import sleep
from prawcore.exceptions import PrawcoreException

class RedditAPI:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.reddit = None
        self.initialize_reddit()
        
    def initialize_reddit(self):
        """Initialize the Reddit API connection"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                username=self.config.username,
                password=self.config.password,
                user_agent=self.config.user_agent
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