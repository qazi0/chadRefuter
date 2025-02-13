import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
from contextlib import contextmanager
import os
import threading

class DatabaseHandler:
    def __init__(self, logger, db_path="data/reddit_bot.db"):
        self.logger = logger
        self.db_path = db_path
        self.lock = threading.Lock()  # Add thread lock
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.initialize_database()

    @contextmanager
    def get_connection(self):
        """Thread-safe context manager for database connections"""
        with self.lock:  # Acquire lock before database operations
            conn = sqlite3.connect(self.db_path)
            try:
                # Enable WAL mode for better concurrency
                conn.execute('PRAGMA journal_mode=WAL')
                yield conn
            finally:
                conn.close()

    def initialize_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create posts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT UNIQUE NOT NULL,
                    subreddit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    post_text TEXT,
                    author TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    llm_response TEXT,
                    response_timestamp DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create comments table for tracking bot's comments
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT NOT NULL,
                    comment_id TEXT UNIQUE NOT NULL,
                    comment_text TEXT NOT NULL,
                    posted_at DATETIME NOT NULL,
                    FOREIGN KEY (post_id) REFERENCES posts(post_id)
                )
            ''')
            
            # Create comment_replies table for tracking conversations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comment_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_comment_id TEXT NOT NULL,
                    reply_comment_id TEXT UNIQUE NOT NULL,
                    reply_text TEXT NOT NULL,
                    author TEXT NOT NULL,
                    conversation_depth INTEGER NOT NULL,
                    llm_response TEXT,
                    is_processed BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_comment_id) REFERENCES comments(comment_id)
                )
            ''')
            
            # Create indices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_id ON posts(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON posts(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_post_id ON comments(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_parent_comment ON comment_replies(parent_comment_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_reply_processed ON comment_replies(is_processed)')
            
            conn.commit()
            self.logger.info("Database initialized successfully")

    def save_post(self, post_id: str, subreddit: str, title: str, 
                 post_text: str, author: str, timestamp: float,
                 llm_response: Optional[str] = None) -> bool:
        """Save a post to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                response_timestamp = datetime.now() if llm_response else None
                
                cursor.execute('''
                    INSERT OR REPLACE INTO posts 
                    (post_id, subreddit, title, post_text, author, timestamp, 
                     llm_response, response_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (post_id, subreddit, title, post_text, author, 
                      datetime.fromtimestamp(timestamp), llm_response, 
                      response_timestamp))
                
                conn.commit()
                self.logger.debug(f"Saved post {post_id} to database")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while saving post {post_id}: {str(e)}")
            return False

    def check_if_post_exists(self, post_id: str) -> bool:
        """Check if a post already exists in the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM posts WHERE post_id = ?', (post_id,))
                return cursor.fetchone() is not None
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while checking post {post_id}: {str(e)}")
            return False

    def fetch_last_n_posts(self, n: int = 5) -> List[Tuple]:
        """Fetch the last n processed posts"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT post_id, title, llm_response, response_timestamp 
                    FROM posts 
                    WHERE llm_response IS NOT NULL 
                    ORDER BY response_timestamp DESC 
                    LIMIT ?
                ''', (n,))
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while fetching last {n} posts: {str(e)}")
            return []

    def update_post_response(self, post_id: str, llm_response: str) -> bool:
        """Update a post with its LLM response"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE posts 
                    SET llm_response = ?, response_timestamp = ? 
                    WHERE post_id = ?
                ''', (llm_response, datetime.now(), post_id))
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while updating post {post_id}: {str(e)}")
            return False

    def save_comment(self, post_id: str, comment_id: str, comment_text: str) -> bool:
        """Save a posted comment to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO comments (post_id, comment_id, comment_text, posted_at)
                    VALUES (?, ?, ?, ?)
                ''', (post_id, comment_id, comment_text, datetime.now()))
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error while saving comment: {str(e)}")
            return False

    def has_commented_on_post(self, post_id: str) -> bool:
        """Check if we've already commented on a post"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM comments WHERE post_id = ?', (post_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.error(f"Database error while checking comment existence: {str(e)}")
            return False

    def save_comment_reply(self, parent_comment_id: str, reply_comment_id: str, 
                          reply_text: str, author: str, conversation_depth: int,
                          llm_response: Optional[str] = None) -> bool:
        """Save a reply to one of the bot's comments"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO comment_replies 
                    (parent_comment_id, reply_comment_id, reply_text, author, 
                     conversation_depth, llm_response, is_processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (parent_comment_id, reply_comment_id, reply_text, author,
                      conversation_depth, llm_response, bool(llm_response)))
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error while saving comment reply: {str(e)}")
            return False

    def get_conversation_depth(self, comment_id: str) -> int:
        """Get the depth of conversation for a comment"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT conversation_depth FROM comment_replies 
                    WHERE reply_comment_id = ?
                ''', (comment_id,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except sqlite3.Error as e:
            self.logger.error(f"Database error while getting conversation depth: {str(e)}")
            return 0

    def is_reply_processed(self, reply_comment_id: str) -> bool:
        """Check if a reply has already been processed"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT is_processed FROM comment_replies 
                    WHERE reply_comment_id = ?
                ''', (reply_comment_id,))
                result = cursor.fetchone()
                return bool(result[0]) if result else False
        except sqlite3.Error as e:
            self.logger.error(f"Database error while checking reply status: {str(e)}")
            return False 