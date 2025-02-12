import logging
import os
from datetime import datetime
import threading
from typing import Optional
from functools import partial

class BotLogger:
    def __init__(self):
        # Create locks for file and console writing
        self.file_lock = threading.Lock()
        self.console_lock = threading.Lock()
        
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Set up logging configuration
        self.logger = logging.getLogger('RedditBot')
        self.logger.setLevel(logging.INFO)
        
        # Create formatters
        self.file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler - gets full messages
        self.file_handler = self._create_file_handler()
        
        # Console handler - gets truncated messages
        self.console_handler = self._create_console_handler()
        
        # Add handlers to logger
        self.logger.addHandler(self.file_handler)
        self.logger.addHandler(self.console_handler)

    def _make_safe_emit(self, original_emit, lock):
        """Create a thread-safe emit function with proper lock binding"""
        def safe_emit(record):
            with lock:
                original_emit(record)
        return safe_emit

    def _create_file_handler(self) -> logging.FileHandler:
        """Create and configure file handler with thread-safe handling"""
        handler = logging.FileHandler(
            f'logs/reddit_bot_{datetime.now().strftime("%Y%m%d")}.log'
        )
        handler.setFormatter(self.file_formatter)
        handler.setLevel(logging.INFO)
        
        # Create thread-safe emit with properly bound lock
        handler.emit = self._make_safe_emit(handler.emit, self.file_lock)
        
        return handler

    def _create_console_handler(self) -> logging.StreamHandler:
        """Create and configure console handler with thread-safe handling"""
        handler = logging.StreamHandler()
        handler.setFormatter(self.console_formatter)
        handler.setLevel(logging.INFO)
        
        # Create thread-safe emit with properly bound lock
        handler.emit = self._make_safe_emit(handler.emit, self.console_lock)
        
        return handler

    def _create_log_record(self, level: int, msg: str) -> logging.LogRecord:
        """Create a LogRecord with proper attributes"""
        return logging.LogRecord(
            name='RedditBot',
            level=level,
            pathname='',
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None
        )

    def _log_dual(self, level: int, full_message: str, console_message: Optional[str] = None):
        """Log different messages to file and console with proper locking"""
        console_message = console_message or full_message
        
        # Create log records
        file_record = self._create_log_record(level, full_message)
        console_record = self._create_log_record(level, console_message)
        
        # Log to file with file lock
        self.file_handler.emit(file_record)
        
        # Log to console with console lock
        self.console_handler.emit(console_record)

    def info(self, message: str, console_message: Optional[str] = None):
        """Thread-safe info logging"""
        self._log_dual(logging.INFO, message, console_message)
        
    def error(self, message: str, exc_info: bool = True):
        """Thread-safe error logging"""
        if exc_info:
            self.logger.error(message, exc_info=exc_info)
        else:
            self._log_dual(logging.ERROR, message)
        
    def warning(self, message: str):
        """Thread-safe warning logging"""
        self._log_dual(logging.WARNING, message)
        
    def debug(self, message: str, console_message: Optional[str] = None):
        """Thread-safe debug logging"""
        self._log_dual(logging.DEBUG, message, console_message) 