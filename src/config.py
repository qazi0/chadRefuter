import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        
        # Reddit API credentials
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.username = os.getenv('USERNAME')
        self.password = os.getenv('PASSWORD')
        self.user_agent = os.getenv('USER_AGENT')
        
        # Bot configuration
        self.subreddit = os.getenv('SUBREDDIT', 'test')  # Default to 'test' subreddit
        self.scan_interval = int(os.getenv('SCAN_INTERVAL', 60))  # Default to 60 seconds
        self.reply_scan_interval = int(os.getenv('REPLY_SCAN_INTERVAL', 300))  # Default to 5 minutes
        self.max_conversations = int(os.getenv('MAX_CONVERSATIONS', 5))
        self.posts_fetch_limit = int(os.getenv('POSTS_FETCH_LIMIT', 5))
        self.post_cache_size = int(os.getenv('POST_CACHE_SIZE', 1000))
        
    def validate(self):
        """Validate that all required configuration is present"""
        required_fields = ['client_id', 'client_secret', 'username', 'password', 'user_agent']
        missing_fields = [field for field in required_fields if not getattr(self, field)]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}") 