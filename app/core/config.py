from pydantic_settings import BaseSettings
from pydantic import Field, validator, SecretStr # Import SecretStr
from typing import Optional, List
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class Settings(BaseSettings):
    # Environment
    environment: Environment = Field(Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # Application
    app_name: str = Field("Prompt Engineering Webapp", env="APP_NAME")
    app_version: str = Field("2.0.0", env="APP_VERSION")
    api_prefix: str = Field("/api/v1", env="API_PREFIX")
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")

    # CORS Configuration
    allowed_hosts: List[str] = Field(["https://yourdomain.com"], env="ALLOWED_HOSTS") # IMPORTANT: Restrict this to your actual production domains!

    # Security Headers
    security_headers: bool = Field(True, env="SECURITY_HEADERS")
    
    # Database - EXACT CONFIGURATION
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(10, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    
    # Redis - EXACT CONFIGURATION
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    redis_max_connections: int = Field(100, env="REDIS_MAX_CONNECTIONS")
    
    # OpenRouter - EXACT CONFIGURATION
    openrouter_api_key: SecretStr = Field(..., env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field("https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL")
    openrouter_timeout: int = Field(60, env="OPENROUTER_TIMEOUT")
    
    # JWT Configuration - FINAL SPECIFICATIONS
    secret_key: SecretStr = Field(..., env="SECRET_KEY") # Use SecretStr for secure handling
    fernet_key: SecretStr = Field(..., env="FERNET_KEY") # Key for Fernet encryption
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")  # HS256 for symmetric key
    jwt_access_expire_minutes: int = Field(15, env="JWT_ACCESS_EXPIRE_MINUTES")  # 15 minutes
    jwt_refresh_expire_days: int = Field(7, env="JWT_REFRESH_EXPIRE_DAYS")  # 7 days
    jwt_issuer: str = Field("prompt-engineering-app", env="JWT_ISSUER")
    jwt_audience: str = Field("prompt-engineering-users", env="JWT_AUDIENCE")
    
    # Rate Limiting - EXACT SPECIFICATIONS FROM ANALYSIS
    rate_limit_global_requests: int = Field(1000, env="RATE_LIMIT_GLOBAL_REQUESTS")  # 1000/hour
    rate_limit_global_window: int = Field(3600, env="RATE_LIMIT_GLOBAL_WINDOW")
    rate_limit_user_requests: int = Field(100, env="RATE_LIMIT_USER_REQUESTS")  # 100/hour
    rate_limit_user_window: int = Field(3600, env="RATE_LIMIT_USER_WINDOW")
    rate_limit_llm_requests: int = Field(30, env="RATE_LIMIT_LLM_REQUESTS")  # 30/minute
    rate_limit_llm_window: int = Field(60, env="RATE_LIMIT_LLM_WINDOW")
    rate_limit_concurrent_users: int = Field(5, env="RATE_LIMIT_CONCURRENT_USERS")  # 5 simultaneous
    
    # AWS Configuration
    aws_region: str = Field("us-east-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(None, env="AWS_SECRET_ACCESS_KEY")
    
    # S3 Configuration
    s3_bucket_name: str = Field("prompt-webapp-storage", env="S3_BUCKET_NAME")
    s3_exports_prefix: str = Field("exports/", env="S3_EXPORTS_PREFIX")
    
    # Monitoring Configuration
    datadog_api_key: Optional[str] = Field(None, env="DATADOG_API_KEY")
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # Business Logic Limits
    max_prompt_length: int = Field(50000, env="MAX_PROMPT_LENGTH")
    max_tokens_per_request: int = Field(4000, env="MAX_TOKENS_PER_REQUEST")
    max_concurrent_requests: int = Field(10, env="MAX_CONCURRENT_REQUESTS")
    max_file_upload_size: int = Field(10 * 1024 * 1024, env="MAX_FILE_UPLOAD_SIZE")  # 10MB
    
    # Celery Configuration
    celery_broker_url: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/1", env="CELERY_RESULT_BACKEND")
    
    @validator('database_url')
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError('Database URL must be PostgreSQL with asyncpg driver')
        return v
    
    @validator('secret_key')
    def validate_secret_key(cls, v: SecretStr):
        secret_value = v.get_secret_value()
        if len(secret_value) < 32:
            raise ValueError('Secret key must be at least 32 characters for adequate entropy.')
        return v
    
    @validator('openrouter_api_key')
    def validate_openrouter_key(cls, v):
        if not v.startswith('sk-or-'):
            raise ValueError('OpenRouter API key must start with sk-or-')
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
settings = Settings()