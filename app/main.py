from fastapi import FastAPI, Request, HTTPException, status # Added Request, HTTPException, status
from fastapi.responses import JSONResponse # New import
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine
from app.models.database import Base
from app.api.routes import router
from app.services.cache import cache_service
from app.services.openrouter import openrouter_service
import logging

from fastapi_guard import SecurityMiddleware, SecurityConfig
from redis import Redis
from fastapi_guard.stores.redis import RedisStore

from app.exceptions.custom_exceptions import APIException, ErrorResponse, InternalServerError # New import

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to DB, create tables, connect to Redis
    logger.info("Application startup: Connecting to database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database connected and tables checked.")

    logger.info("Connecting to Redis cache...")
    await cache_service.connect()
    logger.info("Redis cache connected.")
    # Initialize Redis for fastapi-guard
    app.state.redis_client = cache_service.redis_client
    app.state.rate_limit_store = RedisStore(app.state.redis_client)
    
    # FastAPI Guard Middleware for Global Rate Limiting is added outside lifespan

    logger.info("Validating OpenRouter service configuration...")
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY is not set. OpenRouter service will not function.")
    else:
        logger.info("OpenRouter API key is present.")
    
    yield

    # Shutdown: Disconnect from Redis
    logger.info("Application shutdown: Disconnecting from Redis cache...")
    await cache_service.disconnect()
    logger.info("Redis cache disconnected.")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

# Custom Exception Handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.error(f"API Exception caught: {exc.code} - {exc.message} - Details: {exc.details}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=exc.message, details=exc.details).dict(),
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception caught: {exc.status_code} - {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=f"HTTP_{exc.status_code}_ERROR",
            message=exc.detail,
            details={"headers": exc.headers} if exc.headers else None
        ).dict(),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception caught: {exc}") # Use logger.exception to include traceback
    internal_error = InternalServerError()
    return JSONResponse(
        status_code=internal_error.status_code,
        content=ErrorResponse(code=internal_error.code, message=internal_error.message).dict(),
    )

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI Guard Middleware for Global Rate Limiting
security_config = SecurityConfig(
    rate_limit_store=app.state.rate_limit_store,
    global_rate_limit=(settings.rate_limit_global_requests, settings.rate_limit_global_window),
    concurrent_requests_limit=settings.rate_limit_concurrent_users,
)
app.add_middleware(SecurityMiddleware, config=security_config)

# Security Headers (consider using a reverse proxy for production)
# if settings.security_headers:
#     app.add_middleware(
#         # Example: HSTS, X-Frame-Options, X-Content-Type-Options, etc.
#         # These are often better handled by a reverse proxy like Nginx or a dedicated security library.
#     )

app.include_router(router, prefix=settings.api_prefix)

@app.get("/")
async def root():
    return {"message": "Welcome to the Prompt Engineering Webapp API"}
