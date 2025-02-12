import logging
import os
from datetime import datetime

class BotLogger:
    def __init__(self):
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Set up logging configuration
        self.logger = logging.getLogger('RedditBot')
        self.logger.setLevel(logging.INFO)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler - gets full messages
        file_handler = logging.FileHandler(
            f'logs/reddit_bot_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)
        
        # Console handler - gets truncated messages
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _log_dual(self, level, full_message, console_message=None):
        """Log different messages to file and console"""
        # Get the current logger
        logger = logging.getLogger('RedditBot')
        
        # If no console message is provided, use the full message
        console_message = console_message or full_message
        
        # Store the original handlers
        handlers = logger.handlers[:]
        
        # Log full message to file
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                logger.callHandlers(logging.LogRecord(
                    'RedditBot', level, '', 0, full_message, (), None
                ))
        
        # Log truncated message to console
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                logger.callHandlers(logging.LogRecord(
                    'RedditBot', level, '', 0, console_message, (), None
                ))

    def info(self, message, console_message=None):
        self._log_dual(logging.INFO, message, console_message)
        
    def error(self, message, exc_info=True):
        self.logger.error(message, exc_info=exc_info)
        
    def warning(self, message):
        self.logger.warning(message)
        
    def debug(self, message, console_message=None):
        self._log_dual(logging.DEBUG, message, console_message) 