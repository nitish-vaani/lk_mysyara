import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Application
    APP_NAME: str = "Call Center Management API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "supersecret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./call_center.db"
    DATABASE_CONNECT_DICT: dict = {}
    
    # Redis Configuration
    REDIS_HOST: str = "sbi.vaaniresearch.com"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    
    # Background Tasks
    SYNC_INTERVAL_SECONDS: int = 300  # 5 minutes
    CLEANUP_INTERVAL_HOURS: int = 24
    
    # Analytics
    DEFAULT_PAGINATION_LIMIT: int = 50
    MAX_PAGINATION_LIMIT: int = 1000
    ANALYTICS_RETENTION_DAYS: int = 365
    
    # Export
    MAX_EXPORT_RECORDS: int = 100000
    EXPORT_TIMEOUT_SECONDS: int = 300
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # External Services
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_RETRY_ATTEMPTS: int = 3
    
    # File Storage
    UPLOAD_DIRECTORY: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v:
            raise ValueError("DATABASE_URL is required")
        
        # Set connection dict for SQLite
        if v.startswith("sqlite"):
            cls.DATABASE_CONNECT_DICT = {"check_same_thread": False}
        
        return v
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting"""
        allowed_envs = ["development", "staging", "production", "testing"]
        if v.lower() not in allowed_envs:
            raise ValueError(f"ENVIRONMENT must be one of: {allowed_envs}")
        return v.lower()
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {allowed_levels}")
        return v.upper()
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        ssl_part = "rediss://" if self.REDIS_SSL else "redis://"
        return f"{ssl_part}{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def database_config(self) -> dict:
        """Get database configuration for SQLAlchemy"""
        config = {
            "url": self.DATABASE_URL,
            "echo": self.DEBUG and self.is_development,
        }
        
        if self.DATABASE_CONNECT_DICT:
            config["connect_args"] = self.DATABASE_CONNECT_DICT
        
        return config
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

class DevelopmentSettings(Settings):
    """Development-specific settings"""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    SYNC_INTERVAL_SECONDS: int = 60  # Faster sync for development

class ProductionSettings(Settings):
    """Production-specific settings"""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ALLOWED_HOSTS: List[str] = ["yourdomain.com", "api.yourdomain.com"]
    
    # Production database should be PostgreSQL
    @validator("DATABASE_URL")
    def validate_production_database(cls, v):
        if not v.startswith("postgresql"):
            raise ValueError("Production environment requires PostgreSQL database")
        return v

class TestingSettings(Settings):
    """Testing-specific settings"""
    DATABASE_URL: str = "sqlite:///./test_call_center.db"
    SYNC_INTERVAL_SECONDS: int = 1  # Fast sync for tests
    REDIS_DB: int = 15  # Separate Redis DB for tests

def get_settings() -> Settings:
    """Get settings based on environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    elif env == "development":
        return DevelopmentSettings()
    else:
        return Settings()

# Create global settings instance
settings = get_settings()

# Database configuration for backwards compatibility
DATABASE_URL = settings.DATABASE_URL
SECRET_KEY = settings.SECRET_KEY

# Logging configuration
import logging

def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=settings.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"logs/app_{settings.ENVIRONMENT}.log") 
            if Path("logs").exists() else logging.StreamHandler()
        ]
    )
    
    # Set third-party library log levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )

# Additional configuration classes for different components

class RedisConfig:
    """Redis-specific configuration"""
    
    @staticmethod
    def get_connection_config():
        return {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "password": settings.REDIS_PASSWORD,
            "ssl": settings.REDIS_SSL,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
            "health_check_interval": 30
        }

class SecurityConfig:
    """Security-specific configuration"""
    
    # JWT Configuration
    JWT_ALGORITHM = "HS256"
    JWT_SECRET_KEY = settings.SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    # CORS Configuration
    CORS_ORIGINS = settings.ALLOWED_HOSTS if not settings.is_development else ["*"]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_METHODS = ["*"]
    CORS_ALLOW_HEADERS = ["*"]
    
    # Rate Limiting (if implemented)
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60  # seconds

class MetricsConfig:
    """Metrics and monitoring configuration"""
    
    # Performance thresholds
    SLOW_QUERY_THRESHOLD = 1.0  # seconds
    HIGH_MEMORY_THRESHOLD = 85  # percent
    HIGH_CPU_THRESHOLD = 80     # percent
    
    # Metrics retention
    METRICS_RETENTION_DAYS = 90
    DETAILED_METRICS_RETENTION_DAYS = 30
    
    # Alerting thresholds
    ERROR_RATE_THRESHOLD = 5    # percent
    RESPONSE_TIME_THRESHOLD = 2.0  # seconds

if __name__ == "__main__":
    # Print current configuration
    print("Current Configuration:")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Redis: {settings.redis_url}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"Log Level: {settings.LOG_LEVEL}")
    print(f"API Host: {settings.API_HOST}:{settings.API_PORT}")