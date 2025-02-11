from typing import Set, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RedditPost:
    id: str
    title: str
    body: str
    created_utc: float
    author: str

class PostCache:
    """In-memory cache for processed posts, designed to be easily replaceable with Redis"""
    def __init__(self, max_size: int = 1000):
        self._cache: Set[str] = set()
        self.max_size = max_size
    
    def add(self, post_id: str) -> None:
        """Add a post ID to the cache"""
        if len(self._cache) >= self.max_size:
            # Remove oldest entries if we exceed max size
            # In a Redis implementation, we would use ZREMRANGEBYRANK
            self._cache.clear()
        self._cache.add(post_id)
    
    def contains(self, post_id: str) -> bool:
        """Check if a post ID exists in the cache"""
        return post_id in self._cache

class PostHandler:
    def __init__(self, reddit_api, logger):
        self.reddit_api = reddit_api
        self.logger = logger
        self.post_cache = PostCache()
    
    def fetch_new_posts(self, limit: int = 5) -> List[RedditPost]:
        """Fetch new posts from the subreddit"""
        try:
            subreddit = self.reddit_api.get_subreddit()
            new_posts = []
            
            for post in subreddit.new(limit=limit):
                if not self.post_cache.contains(post.id):
                    reddit_post = RedditPost(
                        id=post.id,
                        title=post.title,
                        body=post.selftext,
                        created_utc=post.created_utc,
                        author=str(post.author)
                    )
                    new_posts.append(reddit_post)
                    self.post_cache.add(post.id)
                    
                    # Log the new post
                    preview = reddit_post.body[:10] + "..." if reddit_post.body else "No body"
                    self.logger.info(
                        f"New post detected - ID: {reddit_post.id}\n"
                        f"Title: {reddit_post.title}\n"
                        f"Preview: {preview}"
                    )
            
            return new_posts
            
        except Exception as e:
            self.logger.error(f"Error fetching new posts: {str(e)}")
            return [] 