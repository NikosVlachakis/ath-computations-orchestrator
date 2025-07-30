"""
Centralized logging configuration for Computations Orchestrator
Self-contained logging that writes to both stdout and host files.
Configurable via environment variables:
- CENTRALIZED_LOGGING_ENABLED: true/false (default: true)
- CENTRALIZED_LOGGING_PATH: host path for logs (default: /app/logs)
"""
import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime


class CentralizedLogger:
    """
    Centralized logging configuration that writes to both stdout and host files.
    Self-contained within each deployment unit.
    """
    
    def __init__(self, service_name: str, log_dir: str = None):
        """
        Initialize centralized logger for a service.
        
        Args:
            service_name: Name of the service (e.g., 'orchestrator', 'vectorization')
            log_dir: Directory where log files will be stored (if None, uses env var or default)
        """
        self.service_name = service_name
        
        # Check if centralized logging is enabled
        self.logging_enabled = os.getenv('CENTRALIZED_LOGGING_ENABLED', 'true').lower() == 'true'
        
        # Get log directory from environment variable or use provided/default
        if log_dir is None:
            log_dir = os.getenv('CENTRALIZED_LOGGING_PATH', '/app/logs')
        
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / f"{service_name}.log"
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging with multiple handlers."""
        # Create logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [{}] %(message)s".format(self.service_name)
        )
        
        # 1. Console handler (stdout) - for Docker logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(detailed_formatter)
        logger.addHandler(console_handler)
        
        # 2. Main log file handler - all logs (only if enabled and directory is writable)
        if self.logging_enabled:
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    self.log_file,
                    maxBytes=50*1024*1024,  # 50MB per file
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(detailed_formatter)
                logger.addHandler(file_handler)
                
                # Log initialization
                logger.info(f"=== {self.service_name.upper()} SERVICE STARTED ===")
                logger.info(f"Logging to: {self.log_file} (all levels: INFO, WARNING, ERROR)")
                logger.info(f"Log path: {self.log_dir}")
                
            except (PermissionError, OSError) as e:
                # If file logging fails, continue with console only
                logger.warning(f"File logging disabled: {e}")
                logger.info(f"=== {self.service_name.upper()} SERVICE STARTED (Console Only) ===")
        else:
            # Centralized logging disabled via environment variable
            logger.info(f"=== {self.service_name.upper()} SERVICE STARTED (Console Only - Centralized Logging Disabled) ===")
        
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    def log_step(self, step_name: str, details: str = ""):
        """Log a processing step."""
        message = f"STEP: {step_name}"
        if details:
            message += f" - {details}"
        logging.info(message)
    
    def log_action(self, action: str, details: str = ""):
        """Log an action being taken."""
        message = f"ACTION: {action}"
        if details:
            message += f" - {details}"
        logging.info(message)
    
    def log_error(self, error_msg: str, exception: Exception = None):
        """Log an error with optional exception details."""
        if exception:
            logging.error(f"ERROR: {error_msg} - Exception: {str(exception)}", exc_info=True)
        else:
            logging.error(f"ERROR: {error_msg}")
    
    def log_success(self, operation: str, details: str = ""):
        """Log a successful operation."""
        message = f"SUCCESS: {operation}"
        if details:
            message += f" - {details}"
        logging.info(message)
    
    def log_warning(self, warning_msg: str):
        """Log a warning."""
        logging.warning(f"WARNING: {warning_msg}")


def setup_service_logging(service_name: str, log_dir: str = "/app/logs") -> CentralizedLogger:
    """
    Setup centralized logging for a service.
    
    Args:
        service_name: Name of the service
        log_dir: Directory where logs will be stored
        
    Returns:
        CentralizedLogger instance
    """
    return CentralizedLogger(service_name, log_dir)


# Utility functions for backward compatibility
def get_logger(service_name: str = "athina"):
    """Get a configured logger instance."""
    return logging.getLogger(service_name)