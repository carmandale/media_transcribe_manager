"""
Centralized logging configuration for the Scribe system.
This module provides consistent logging setup across all scripts and modules.
"""
import os
import logging
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

def setup_logger(logger_name, log_file=None, level=logging.INFO, console=True):
    """
    Set up a logger with file and console handlers.
    
    Args:
        logger_name (str): Name of the logger
        log_file (str, optional): Log file name. If None, uses logger_name + '.log'. 
        level (int, optional): Logging level. Defaults to logging.INFO.
        console (bool, optional): Whether to log to console. Defaults to True.
        
    Returns:
        logging.Logger: Configured logger
    """
    if log_file is None:
        log_file = f"{logger_name}.log"
    
    # Convert to path in logs directory
    log_path = LOG_DIR / log_file
    
    # Get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add file handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def get_script_logger(script_name=None):
    """
    Get a logger for a script with the script's name.
    
    Args:
        script_name (str, optional): Script name. If None, uses the calling module name.
        
    Returns:
        logging.Logger: Configured logger
    """
    if script_name is None:
        # Get the name of the calling module
        import inspect
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        script_name = os.path.basename(module.__file__).replace('.py', '')
    
    return setup_logger(script_name)