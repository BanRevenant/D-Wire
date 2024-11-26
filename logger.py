import logging
import os

def setup_logger(name, log_file, level=logging.INFO):
    """
    Sets up a logger with a file handler and a stream handler.
    Ensures the log directory exists to avoid errors.

    Args:
        name (str): Name of the logger.
        log_file (str): Path to the log file.
        level (int): Logging level (default: logging.INFO).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Ensure the log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:  # Check if the directory part of the path is not empty
        os.makedirs(log_dir, exist_ok=True)

    # Create handlers
    f_handler = logging.FileHandler(log_file)
    c_handler = logging.StreamHandler()

    # Set levels for handlers
    f_handler.setLevel(level)
    c_handler.setLevel(level)

    # Define log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_handler.setFormatter(formatter)
    c_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(f_handler)
    logger.addHandler(c_handler)

    return logger
