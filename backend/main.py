# backend/main.py - Main FastAPI application with full functionality

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.gzip import GzipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import our modules
from models import create_database, init_default_data
from routes import router as api_router
from services import background_sync_task, RedisService, DataSyncService
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for background tasks
background_task = None
redis_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    
    # Startup
    logger.info("🚀 Starting Call Center Backend API")
    
    # Initialize database
    logger.info("📊 Initializing database...")
    create_database()
    init_default_data()
    
    # Initialize Redis service
    global redis_service
    redis_service = RedisService()
    connected = await redis_service.connect()
    if connected:
        logger.info("✅ Redis connection established")
    else:
        logger.warning("⚠️ Redis connection failed - some features may be limited")
    
    # Start background sync task
    global background_task
    background_task = asyncio.create_task(background_sync_task())
    logger.info("🔄 Background sync task started")
    
    logger.info("✅ Application startup complete")
    logger.info("📋 API Documentation: http://localhost:8000/docs")
    logger.info("🔧 Health Check: http://localhost:8000/health")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Call Center Backend API")
    
    # Cancel background task
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass
    
    # Close Redis connection
    if redis_service:
        await redis_service.close()
    
    logger.info("✅ Shutdown complete")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="Call Center Management API",
    description="""
    Comprehensive Call Center Management System API
    
    ## Features
    
    * **Dashboard Analytics** - High-level metrics and trends
    * **Call Management** - Complete call history with filtering
    * **Real-time Data** - Integration with Redis for live updates
    * **Export Functionality** - CSV export with custom filters
    * **Webhook Support** - Flexible webhook endpoints for data ingestion
    * **Performance Metrics** - Detailed call performance analytics
    * **Extensible Design** - Easy to add new features and integrations
    
    ## Authentication
    
    Currently uses simple token-based authentication. 
    Use `testtoken` as the Bearer token for API access.
    
    ## Data Sources
    
    * **Database** - PostgreSQL/SQLite for persistent storage
    * **Redis** - Real-time data from LiveKit agents
    * **Webhooks** - External system integrations
    
    """,
    version="1.0.0",
    contact={
        "name": "Call Center API Support",
        "email": "support@company.com",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(GzipMiddleware, minimum_size=1000)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error responses"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, 'request_id', 'unknown')
        }
    )

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID for tracking"""
    import uuid
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Include API routes
app.include_router(api_router)

# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """System health check"""
    
    # Check Redis connection
    redis_status = "connected"
    try:
        if redis_service:
            await redis_service.redis_client.ping()
    except:
        redis_status = "disconnected"
    
    # Check background task
    background_task_status = "running" if background_task and not background_task.done() else "stopped"
    
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",  # Will be current time in production
        "version": "1.0.0",
        "services": {
            "database": "connected",
            "redis": redis_status,
            "background_sync": background_task_status
        },
        "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "development"
    }

# Root endpoint
@app.get("/", tags=["System"])
async def read_root():
    """API root endpoint"""
    return {
        "message": "Call Center Management API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "api": "/api/v1"
    }

# Additional utility endpoints
@app.post("/api/v1/admin/sync-redis", tags=["Admin"])
async def manual_redis_sync():
    """Manually trigger Redis sync (admin only)"""
    
    try:
        sync_service = DataSyncService(redis_service)
        await sync_service.sync_pending_calls()
        await sync_service.process_enhanced_metrics()
        
        return {
            "status": "success",
            "message": "Redis sync completed successfully"
        }
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@app.get("/api/v1/admin/system-info", tags=["Admin"])
async def get_system_info():
    """Get detailed system information (admin only)"""
    
    import psutil
    import os
    
    return {
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "percent": psutil.disk_usage('/').percent
            }
        },
        "process": {
            "pid": os.getpid(),
            "threads": psutil.Process().num_threads(),
            "memory_info": psutil.Process().memory_info()._asdict()
        },
        "database_url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "sqlite",
        "redis_connected": redis_service and redis_service.redis_client is not None
    }

# Custom startup event for additional initialization
@app.on_event("startup")
async def additional_startup():
    """Additional startup tasks"""
    logger.info("🔧 Running additional startup tasks...")
    
    # You can add more startup tasks here
    # For example: warming up ML models, checking external services, etc.
    
    logger.info("✅ Additional startup tasks completed")

if __name__ == "__main__":
    # Development server configuration
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=1236,
        reload=True,
        log_level="info",
        access_log=True
    )