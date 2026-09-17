import json
import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Custom formatter providing structured JSON or consistent key-value logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Include custom extra attributes if present
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "msg", "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName"
            } and not key.startswith("_"):
                log_obj[key] = value

        return json.dumps(log_obj)


def setup_logger(name: str = "global_intel", level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Configure and return a structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if json_format:
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s UTC [%(levelname)s] [%(name)s]: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        logger.addHandler(handler)
    
    return logger


logger = setup_logger()
get_logger = setup_logger
