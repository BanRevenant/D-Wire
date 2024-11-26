import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# For Windows support
if os.name == 'nt':
    import colorama
    colorama.init()

class ColorFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'DEBUG': '\033[37m',  # White
        'INFO': '\033[94m',   # Blue
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m',   # Red
        'CRITICAL': '\033[41m',# Red background
        'RESET': '\033[0m'    # Reset color
    }

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)

    def format(self, record):
        # Save original format
        original_fmt = self._style._fmt

        # Add color to the level name
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"

        # Add color to the entire message for ERROR and CRITICAL
        if record.levelno in [logging.ERROR, logging.CRITICAL]:
            self._style._fmt = f"{self.COLORS['ERROR']}{original_fmt}{self.COLORS['RESET']}"
        # Add color to the entire message for WARNING
        elif record.levelno == logging.WARNING:
            self._style._fmt = f"{self.COLORS['WARNING']}{original_fmt}{self.COLORS['RESET']}"
        # Add color to the entire message for INFO
        elif record.levelno == logging.INFO:
            self._style._fmt = f"{self.COLORS['INFO']}{original_fmt}{self.COLORS['RESET']}"

        # Format the record
        result = super().format(record)

        # Restore original format
        self._style._fmt = original_fmt

        return result

def setup_logger(name, log_file, level=logging.INFO):
    """Set up a logger with both file and console output"""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Remove existing handlers to prevent duplicate logs
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = ColorFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler (with rotation)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
        
    except Exception as e:
        print(f"Error setting up logger: {str(e)}")
        # Create a basic console logger as fallback
        basic_logger = logging.getLogger(name)
        basic_logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        basic_logger.addHandler(handler)
        return basic_logger

# Optional: Set up a default logger if needed
def get_default_logger():
    return setup_logger('default', 'logs/default.log')