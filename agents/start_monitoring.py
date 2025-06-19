#!/usr/bin/env python3
"""Start monitoring API - CUSTOMIZED"""

import sys
import os
sys.path.append('.')

if __name__ == "__main__":
    from monitoring.simple_api import app, config
    import uvicorn
    
    print(f"🚀 Starting monitoring on port {config.monitoring_port}")
    print(f"📊 Dashboard: http://localhost:{config.monitoring_port}")
    print(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    
    uvicorn.run(
        app, 
        host=config.monitoring_host, 
        port=config.monitoring_port,
        log_level="info"
    )
