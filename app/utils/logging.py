import logging
import structlog
from app.core.config import settings

def configure_logging():
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ]

    logging.basicConfig(format="%(message)s", level=settings.log_level)

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Optionally add a console renderer for development
    if settings.debug:
        logging.getLogger().handlers[0].setFormatter(structlog.dev.ConsoleRenderer(colors=True))

# Example usage (can be removed later)
# logger = structlog.get_logger()
# logger.info("Logging configured", environment=settings.environment)