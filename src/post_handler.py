from typing import Set, Optional, Dict, List, Type
from dataclasses import dataclass
from datetime import datetime
from llm_handler import LLMHandler, OllamaHandler
from database import DatabaseHandler
import time

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
    def __init__(self, reddit_api, logger, llm_handler: Optional[LLMHandler] = None):
        self.reddit_api = reddit_api
        self.logger = logger
        self.post_cache = PostCache()
        
        # Try to initialize the LLM handler
        try:
            self.llm_handler = llm_handler or OllamaHandler(logger)
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM handler: {str(e)}")
            self.llm_handler = None
        
        self.db = DatabaseHandler(logger)
    
    def fetch_new_posts(self, limit: int = 5) -> List[RedditPost]:
        """Fetch new posts from the subreddit"""
        try:
            subreddit = self.reddit_api.get_subreddit()
            new_posts = []
            
            for post in subreddit.new(limit=limit):
                # Check both cache and database
                if not self.post_cache.contains(post.id) and not self.db.check_if_post_exists(post.id):
                    reddit_post = RedditPost(
                        id=post.id,
                        title=post.title,
                        body=post.selftext,
                        created_utc=post.created_utc,
                        author=str(post.author)
                    )
                    new_posts.append(reddit_post)
                    self.post_cache.add(post.id)
                    
                    # Save to database without response
                    self.db.save_post(
                        post_id=post.id,
                        subreddit=self.reddit_api.config.subreddit,
                        title=post.title,
                        post_text=post.selftext,
                        author=str(post.author),
                        timestamp=post.created_utc
                    )
                    
                    # Create full and truncated log messages
                    full_message = (
                        f"New post detected - ID: {reddit_post.id}\n"
                        f"Title: {reddit_post.title}\n"
                        f"Body: {reddit_post.body}"
                    )
                    
                    console_message = (
                        f"New post detected - ID: {reddit_post.id}\n"
                        f"Title: {reddit_post.title[:50]}{'...' if len(reddit_post.title) > 50 else ''}\n"
                        f"Preview: {reddit_post.body[:50]}{'...' if len(reddit_post.body) > 50 else ''}"
                    )
                    
                    self.logger.info(full_message, console_message)
            
            return new_posts
            
        except Exception as e:
            self.logger.error(f"Error fetching new posts: {str(e)}")
            return [] 

    async def process_post(self, post: RedditPost) -> Optional[str]:
        """Process a post through the LLM and post comment if appropriate"""
        try:
            # Skip if we've already commented
            if self.db.has_commented_on_post(post.id):
                self.logger.debug(f"Already commented on post {post.id}, skipping")
                return None

            # Check if LLM handler is available
            if not self.llm_handler:
                self.logger.error("No LLM handler available")
                return None

            # Check if post is purely religious discussion
            religious_keywords = {
                'god', 'gods', 'religion', 'worship', 'prayer', 'temple', 
                'church', 'mosque', 'scripture', 'divine', 'prophet', 'bible',
                'quran', 'torah', 'holy'
            }
            
            post_text = f"{post.title.lower()} {post.body.lower()}"
            word_count = len(post_text.split())
            religious_word_count = sum(1 for word in religious_keywords if word in post_text)
            
            # If post is predominantly religious (>40% religious terms), skip it
            if religious_word_count > 0 and (religious_word_count / word_count) > 0.4:
                self.logger.info(
                    f"Skipping purely religious post {post.id}",
                    f"Post {post.id} skipped - religious content"
                )
                return "That's between you and your faith, mate. Not my place to intervene."
            
            prompt = (
                f"As Thomas Shelby, provide a response to this Reddit post that demonstrates "
                f"your commanding presence and unbreakable logic, and demolishes this post and antagonizes the poster. Remember to avoid any form of religious discrimination.\n\n"
                f"Title: {post.title}\n"
                f"Content: {post.body}\n\n"
                "Your response (maintain your character's tone and wisdom, and demeanour):"
            )
            
            response = await self.llm_handler.generate_response(prompt)
            
            if response and response.text:
                # Check for discriminatory content
                discriminatory_terms = {'religious discrimination', 'discrimination'}
                response_lower = response.text.lower()
                
                if any(term in response_lower for term in discriminatory_terms):
                    self.logger.warning(
                        f"Rejected discriminatory response for post {post.id}: {response.text}",
                        f"Rejected discriminatory response for post {post.id}"
                    )
                    return None
                
                # Update database with the response
                self.db.update_post_response(post.id, response.text)
                
                # Return the response without posting the comment
                return response.text
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error processing post {post.id} through LLM: {str(e)}")
            return None

    async def process_reply(self, reply_text: str, depth: int) -> Optional[str]:
        """Process a reply and generate a response"""
        try:
            # Add conversation depth context to the prompt
            context = f"This is reply #{depth} in the conversation. "
            prompt = f"{context}Please respond to this comment: {reply_text}"
            
            response = await self.llm_handler.generate_response(prompt)
            return response.text if response else None
            
        except Exception as e:
            self.logger.error(f"Error processing reply: {str(e)}")
            return None

    async def close(self):
        """Cleanup resources"""
        await self.llm_handler.close() 