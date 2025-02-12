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
            
            # Create indices for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_id ON posts(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON posts(timestamp)')
            
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