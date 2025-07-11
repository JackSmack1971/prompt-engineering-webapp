from contextlib import asynccontextmanager
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator # Added for type hinting consistency
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from fastapi_guard import SecurityMiddleware, SecurityConfig
from redis import Redis
from fastapi_guard.stores.redis import RedisStore

# Initialize SecurityConfig globally, rate_limit_store will be set in lifespan
security_config = SecurityConfig(
    global_rate_limit=(settings.rate_limit_global_requests, settings.rate_limit_global_window),
    concurrent_requests_limit=settings.rate_limit_concurrent_users,
)

from app.core.config import settings
from app.core.database import engine
from app.models.database import Base
from app.api.routes import router
from app.services.cache import CacheService
from app.services.openrouter import OpenRouterService # Import the class, not the instance
from app.exceptions.custom_exceptions import APIException, ErrorResponse, InternalServerError

# Dependency for CacheService
def get_cache_service() -> CacheService:
    return app.state.cache_service

# Dependency for OpenRouterService
def get_openrouter_service() -> OpenRouterService:
    return app.state.openrouter_service

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
    # Create CacheService instance and manage its lifecycle
    app.state.cache_service = CacheService()
    await app.state.cache_service.connect()
    logger.info("Redis cache connected.")
    
    # Initialize Redis for fastapi-guard using the same client from CacheService
    app.state.redis_client = app.state.cache_service.redis_client
    app.state.rate_limit_store = RedisStore(app.state.redis_client)
    
    # Set the rate limit store for SecurityConfig
    security_config.rate_limit_store = app.state.rate_limit_store

    logger.info("Initializing OpenRouter service...")
    app.state.openrouter_service = OpenRouterService()
    app.state.openrouter_service.cache_service = app.state.cache_service # Inject CacheService into OpenRouterService
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY is not set. OpenRouter service will not function.")
    else:
        logger.info("OpenRouter API key is present.")
    
    yield

    # Shutdown: Disconnect from Redis
    logger.info("Application shutdown: Disconnecting from Redis cache...")
    if app.state.cache_service:
        await app.state.cache_service.disconnect()
    logger.info("Redis cache disconnected.")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

# Add SecurityMiddleware here, after app creation but before lifespan execution
app.add_middleware(SecurityMiddleware, config=security_config)

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if settings.security_headers:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            # A more robust CSP would be generated dynamically based on allowed sources.
            # This is a basic example.
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self';"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(router, prefix=settings.api_prefix)

@app.get("/")
async def root():
    return {"message": "Welcome to the Prompt Engineering Webapp API"}
