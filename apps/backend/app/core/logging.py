import logging
import sys
from typing import Any
from datetime import datetime
import json

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output (development)
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    _BUILTIN_KEYS = frozenset(logging.LogRecord(
        None, None, "", 0, "", (), None
    ).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        message = super().format(record)

        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._BUILTIN_KEYS
        }
        if extras:
            message += " | " + " ".join(f"{k}={v}" for k, v in extras.items())

        return f"{timestamp} | {message}"


def setup_logging():
    """
    Configure logging for the application
    """
    
    # Root logger at WARNING — keeps all third-party libraries quiet by default
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if settings.ENVIRONMENT == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter('%(levelname)s | %(name)s | %(message)s'))

    root_logger.addHandler(console_handler)

    # App logger at DEBUG/INFO — only our code is verbose
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    app_logger.info(
        f"Logging configured - Environment: {settings.ENVIRONMENT}, "
        f"Level: {'DEBUG' if settings.DEBUG else 'INFO'}"
    )


# Create logger instance
logger = logging.getLogger("app")


_RESERVED_LOG_KEYS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
})


class LoggerAdapter:
    """
    Logger adapter with convenience methods
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs):
        """Log with extra fields, guarding against reserved LogRecord key names."""
        extra = {}
        for key, value in kwargs.items():
            safe_key = f"extra_{key}" if key in _RESERVED_LOG_KEYS else key
            extra[safe_key] = value
        self.logger.log(level, message, extra=extra)


# Export configured logger
logger_adapter = LoggerAdapter(logger)