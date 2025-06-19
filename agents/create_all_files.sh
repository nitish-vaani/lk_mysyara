#!/bin/bash
# create_customized_files.sh - Customized for your Redis and ports

echo "🚀 Creating LiveKit Metrics System - Customized for Your Environment"
echo "Redis: sbi.vaaniresearch.com:6379 (DB 15)"
echo "Ports: 1234-1247 available"
echo ""

# Create directory structure
echo "📁 Creating directories..."
mkdir -p config
mkdir -p metrics
mkdir -p monitoring
mkdir -p logs
mkdir -p tools

# Install dependencies
echo "📦 Installing dependencies..."
pip install redis aioredis psutil fastapi uvicorn pyyaml

# 1. Create config/metrics_config.py - CUSTOMIZED
echo "📝 Creating config/metrics_config.py..."
cat > config/metrics_config.py << 'EOF'
import os
from dataclasses import dataclass
from typing import Optional
import yaml
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MetricsConfig:
    """Centralized metrics configuration - Customized for your environment"""
    
    # Core Settings
    enabled: bool = True
    agent_name: str = "outbound-caller"
    
    # Redis Configuration - CUSTOMIZED for your setup
    redis_host: str = "sbi.vaaniresearch.com"
    redis_port: int = 6379
    redis_db: int = 15  # Using DB 15 to avoid conflicts
    redis_ttl_hours: int = 24
    
    # Database Configuration
    database_enabled: bool = False
    database_type: str = "none"
    database_url: Optional[str] = None
    
    # Monitoring API - CUSTOMIZED for your available ports
    monitoring_enabled: bool = True
    monitoring_port: int = 1234  # Using your available port
    monitoring_host: str = "0.0.0.0"
    
    # Collection Settings
    collect_system_metrics: bool = True
    collect_call_metrics: bool = True
    system_metrics_interval: int = 60
    
    # Performance Thresholds
    cpu_warning_threshold: float = 75.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 90.0
    
    # Load Testing
    max_concurrent_calls: int = 50
    target_calls_for_test: int = 500
    
    # Logging
    log_level: str = "INFO"
    detailed_logging: bool = False
    
    @classmethod
    def from_env(cls) -> 'MetricsConfig':
        """Create config from environment variables"""
        return cls(
            enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            agent_name=os.getenv("AGENT_NAME", "outbound-caller"),
            redis_host=os.getenv("REDIS_HOST", "sbi.vaaniresearch.com"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "15")),
            database_enabled=os.getenv("DATABASE_ENABLED", "false").lower() == "true",
            monitoring_port=int(os.getenv("MONITORING_PORT", "1234")),
            max_concurrent_calls=int(os.getenv("MAX_CONCURRENT_CALLS", "50")),
            target_calls_for_test=int(os.getenv("TARGET_CALLS_FOR_TEST", "500")),
            log_level=os.getenv("METRICS_LOG_LEVEL", "INFO"),
        )
    
    @classmethod
    def from_yaml(cls, config_file: str = "config/metrics.yml") -> 'MetricsConfig':
        """Create config from YAML file"""
        if not os.path.exists(config_file):
            default_config = cls()
            default_config.save_to_yaml(config_file)
            return default_config
        
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def save_to_yaml(self, config_file: str = "config/metrics.yml"):
        """Save current config to YAML file"""
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        config_dict = {
            'enabled': self.enabled,
            'agent_name': self.agent_name,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'redis_db': self.redis_db,
            'database_enabled': self.database_enabled,
            'monitoring_port': self.monitoring_port,
            'collect_system_metrics': self.collect_system_metrics,
            'collect_call_metrics': self.collect_call_metrics,
            'system_metrics_interval': self.system_metrics_interval,
            'cpu_warning_threshold': self.cpu_warning_threshold,
            'memory_warning_threshold': self.memory_warning_threshold,
            'max_concurrent_calls': self.max_concurrent_calls,
            'target_calls_for_test': self.target_calls_for_test,
            'log_level': self.log_level,
            'detailed_logging': self.detailed_logging
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

# Global configuration instance
_config = None

def get_metrics_config() -> MetricsConfig:
    """Get the global metrics configuration"""
    global _config
    if _config is None:
        try:
            _config = MetricsConfig.from_yaml()
        except:
            _config = MetricsConfig.from_env()
    return _config

def reload_config():
    """Reload configuration"""
    global _config
    _config = None
    return get_metrics_config()
EOF

# 2. Create metrics/simple_recorder.py - CUSTOMIZED for your Redis
echo "📝 Creating metrics/simple_recorder.py..."
cat > metrics/simple_recorder.py << 'EOF'
import asyncio
import json
import time
import logging
import psutil
import redis.asyncio as redis
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.metrics_config import get_metrics_config

logger = logging.getLogger("metrics")

@dataclass
class SimpleCallMetrics:
    """Simplified call metrics for Redis-only mode"""
    call_id: str
    room_name: str
    agent_name: str
    start_time: float
    phone_number: str = ""
    
    # Counters
    llm_calls: int = 0
    tts_calls: int = 0
    asr_calls: int = 0
    
    # Latencies (keep last 10 for simplicity)
    llm_ttft_times: List[float] = None
    user_latencies: List[float] = None
    
    # Status
    status: str = "active"
    end_time: Optional[float] = None
    
    def __post_init__(self):
        if self.llm_ttft_times is None:
            self.llm_ttft_times = []
        if self.user_latencies is None:
            self.user_latencies = []

@dataclass  
class SystemMetrics:
    """Simple system metrics"""
    timestamp: float
    agent_name: str
    cpu_percent: float
    memory_percent: float
    active_calls: int
    uptime_seconds: float

class SimpleMetricsRecorder:
    """Minimal metrics recorder - CUSTOMIZED for your Redis setup"""
    
    def __init__(self):
        self.config = get_metrics_config()
        self.redis_client = None
        self.active_calls: Dict[str, SimpleCallMetrics] = {}
        self.start_time = time.time()
        self.system_monitor_task = None
        
        log_level = getattr(logging, self.config.log_level.upper())
        logger.setLevel(log_level)
        
        if self.config.enabled:
            logger.info(f"🎯 SimpleMetricsRecorder initialized for {self.config.agent_name}")
            logger.info(f"🔧 Redis: {self.config.redis_host}:{self.config.redis_port}/db{self.config.redis_db}")
        else:
            logger.info("📊 Metrics disabled by configuration")
    
    async def initialize(self):
        """Initialize Redis connection - CUSTOMIZED for your setup"""
        if not self.config.enabled:
            return
        
        try:
            # CUSTOMIZED: Connect to your Redis with specific DB
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,  # Using DB 15 to avoid conflicts
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info(f"✅ Redis connection established: {self.config.redis_host}:{self.config.redis_port}/db{self.config.redis_db}")
            
            if self.config.collect_system_metrics:
                self.system_monitor_task = asyncio.create_task(self._monitor_system())
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            logger.warning("⚠️ Continuing without metrics")
    
    async def start_call(self, room_name: str, phone_number: str = "") -> str:
        """Start tracking a call"""
        if not self.config.enabled or not self.config.collect_call_metrics:
            return f"disabled_{room_name}"
        
        call_id = f"{room_name}_{int(time.time())}"
        
        call_metrics = SimpleCallMetrics(
            call_id=call_id,
            room_name=room_name,
            agent_name=self.config.agent_name,
            start_time=time.time(),
            phone_number=phone_number
        )
        
        self.active_calls[call_id] = call_metrics
        await self._store_call_redis(call_id, call_metrics)
        
        logger.info(f"📞 Started tracking call: {call_id}")
        return call_id
    
    async def end_call(self, call_id: str, status: str = "completed"):
        """End call tracking"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.end_time = time.time()
        call_metrics.status = status
        
        await self._store_call_redis(call_id, call_metrics)
        await self._store_completed_call(call_id, call_metrics)
        
        del self.active_calls[call_id]
        
        duration = call_metrics.end_time - call_metrics.start_time
        logger.info(f"📞 Ended call: {call_id} (status: {status}, duration: {duration:.1f}s)")
    
    async def record_llm_metric(self, call_id: str, ttft: float):
        """Record LLM TTFT"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        metrics = self.active_calls[call_id]
        metrics.llm_calls += 1
        metrics.llm_ttft_times.append(ttft)
        if len(metrics.llm_ttft_times) > 10:
            metrics.llm_ttft_times.pop(0)
        
        if self.config.detailed_logging:
            logger.debug(f"🧠 LLM TTFT: {ttft:.3f}s for {call_id}")
    
    async def record_tts_metric(self, call_id: str):
        """Record TTS call"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        metrics = self.active_calls[call_id]
        metrics.tts_calls += 1
    
    async def record_asr_metric(self, call_id: str):
        """Record ASR call"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        metrics = self.active_calls[call_id]
        metrics.asr_calls += 1
    
    async def record_user_latency(self, call_id: str, latency: float):
        """Record user-experienced latency"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        metrics = self.active_calls[call_id]
        metrics.user_latencies.append(latency)
        if len(metrics.user_latencies) > 10:
            metrics.user_latencies.pop(0)
        
        logger.info(f"⏱️ User latency: {latency:.3f}s for {call_id}")
    
    async def get_live_stats(self) -> dict:
        """Get current live statistics"""
        if not self.config.enabled:
            return {"enabled": False}
        
        total_active = len(self.active_calls)
        total_llm_calls = sum(call.llm_calls for call in self.active_calls.values())
        total_tts_calls = sum(call.tts_calls for call in self.active_calls.values())
        
        all_ttft = []
        all_user_latencies = []
        
        for call in self.active_calls.values():
            all_ttft.extend(call.llm_ttft_times)
            all_user_latencies.extend(call.user_latencies)
        
        avg_ttft = sum(all_ttft) / len(all_ttft) if all_ttft else 0
        avg_user_latency = sum(all_user_latencies) / len(all_user_latencies) if all_user_latencies else 0
        
        return {
            "enabled": True,
            "agent_name": self.config.agent_name,
            "active_calls": total_active,
            "total_llm_calls": total_llm_calls,
            "total_tts_calls": total_tts_calls,
            "avg_ttft_seconds": round(avg_ttft, 3),
            "avg_user_latency_seconds": round(avg_user_latency, 3),
            "uptime_seconds": time.time() - self.start_time,
        }
    
    async def _store_call_redis(self, call_id: str, metrics: SimpleCallMetrics):
        """Store call in Redis with proper key prefix"""
        if not self.redis_client:
            return
        
        try:
            # Use prefix to avoid conflicts with your existing pub-sub
            key = f"livekit_metrics:call:{call_id}"
            data = json.dumps(asdict(metrics), default=str)
            ttl = self.config.redis_ttl_hours * 3600
            await self.redis_client.setex(key, ttl, data)
        except Exception as e:
            logger.warning(f"Failed to store call in Redis: {e}")
    
    async def _store_completed_call(self, call_id: str, metrics: SimpleCallMetrics):
        """Store completed call for analytics"""
        if not self.redis_client:
            return
        
        try:
            # Use prefix to avoid conflicts
            key = "livekit_metrics:completed_calls"
            data = json.dumps(asdict(metrics), default=str)
            await self.redis_client.lpush(key, data)
            await self.redis_client.ltrim(key, 0, 999)
            await self.redis_client.expire(key, 7 * 24 * 3600)
        except Exception as e:
            logger.warning(f"Failed to store completed call: {e}")
    
    async def _monitor_system(self):
        """Monitor system metrics"""
        while True:
            try:
                system_metrics = SystemMetrics(
                    timestamp=time.time(),
                    agent_name=self.config.agent_name,
                    cpu_percent=psutil.cpu_percent(interval=1),
                    memory_percent=psutil.virtual_memory().percent,
                    active_calls=len(self.active_calls),
                    uptime_seconds=time.time() - self.start_time
                )
                
                if self.redis_client:
                    # Use prefix to avoid conflicts
                    key = f"livekit_metrics:system:{self.config.agent_name}"
                    data = json.dumps(asdict(system_metrics), default=str)
                    await self.redis_client.setex(key, 300, data)
                
                if system_metrics.cpu_percent > self.config.cpu_warning_threshold:
                    logger.warning(f"🔥 High CPU: {system_metrics.cpu_percent:.1f}%")
                
                if system_metrics.memory_percent > self.config.memory_warning_threshold:
                    logger.warning(f"🧠 High Memory: {system_metrics.memory_percent:.1f}%")
                
                await asyncio.sleep(self.config.system_metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.system_monitor_task:
            self.system_monitor_task.cancel()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("🧹 Metrics recorder cleaned up")

# Global instance
_recorder = None

async def initialize_simple_metrics(agent_name: str = None):
    """Initialize the simple metrics system"""
    global _recorder
    
    if agent_name:
        config = get_metrics_config()
        config.agent_name = agent_name
    
    _recorder = SimpleMetricsRecorder()
    await _recorder.initialize()
    return _recorder

def get_simple_recorder() -> SimpleMetricsRecorder:
    """Get the metrics recorder"""
    global _recorder
    if _recorder is None:
        raise RuntimeError("Simple metrics not initialized")
    return _recorder
EOF

# 3. Create config/metrics.yml - CUSTOMIZED
echo "📝 Creating config/metrics.yml..."
cat > config/metrics.yml << 'EOF'
# LiveKit Metrics Configuration - CUSTOMIZED for your environment
enabled: true
agent_name: "outbound-caller"

# Redis Configuration - CUSTOMIZED for your setup
redis_host: "sbi.vaaniresearch.com"
redis_port: 6379
redis_db: 15  # Using DB 15 to avoid conflicts with your pub-sub

# Database (disabled for quick start)
database_enabled: false

# Monitoring - CUSTOMIZED for your available ports
monitoring_enabled: true
monitoring_port: 1234  # Using your available port
monitoring_host: "0.0.0.0"

# Collection Settings
collect_system_metrics: true
collect_call_metrics: true
system_metrics_interval: 30

# Performance Thresholds for 500 calls
cpu_warning_threshold: 70.0
cpu_critical_threshold: 85.0
memory_warning_threshold: 75.0
memory_critical_threshold: 90.0

# Load Testing Configuration
max_concurrent_calls: 50
target_calls_for_test: 500

# Logging
log_level: "INFO"
detailed_logging: false
EOF

# 4. Create monitoring API - CUSTOMIZED
echo "📝 Creating monitoring/simple_api.py..."
cat > monitoring/simple_api.py << 'EOF'
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import redis.asyncio as redis
from datetime import datetime
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.metrics_config import get_metrics_config
import logging

logger = logging.getLogger("monitoring_api")

app = FastAPI(
    title="LiveKit Metrics - Customized",
    description="Load testing metrics for your environment",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = get_metrics_config()
redis_client = None

@app.on_event("startup")
async def startup():
    global redis_client
    try:
        # CUSTOMIZED: Connect to your Redis setup
        redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"✅ Monitoring API connected to Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # CUSTOMIZED: Use prefixed keys
        system_key = f"livekit_metrics:system:{config.agent_name}"
        system_data = await redis_client.get(system_key)
        
        call_keys = await redis_client.keys("livekit_metrics:call:*")
        active_calls = 0
        call_details = []
        
        for key in call_keys:
            call_data = await redis_client.get(key)
            if call_data:
                call = json.loads(call_data)
                if call.get("status") == "active":
                    active_calls += 1
                    duration = datetime.now().timestamp() - call["start_time"]
                    call_details.append({
                        "room_name": call["room_name"],
                        "duration_seconds": round(duration, 1),
                        "llm_calls": call.get("llm_calls", 0),
                        "phone_number": call.get("phone_number", "")
                    })
        
        system_metrics = {}
        if system_data:
            system_metrics = json.loads(system_data)
        
        return {
            "agent_name": config.agent_name,
            "active_calls": active_calls,
            "max_concurrent": config.max_concurrent_calls,
            "utilization_percent": round((active_calls / config.max_concurrent_calls) * 100, 1),
            "system_metrics": system_metrics,
            "active_call_details": call_details,
            "redis_info": f"{config.redis_host}:{config.redis_port}/db{config.redis_db}",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status")

@app.get("/api/performance")
async def get_performance():
    """Get performance analytics from completed calls"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # CUSTOMIZED: Use prefixed keys
        completed_data = await redis_client.lrange("livekit_metrics:completed_calls", 0, -1)
        
        if not completed_data:
            return {
                "total_calls": 0,
                "performance_summary": {},
                "timestamp": datetime.now()
            }
        
        calls = [json.loads(call) for call in completed_data]
        
        total_calls = len(calls)
        completed_calls = len([c for c in calls if c.get("status") == "completed"])
        success_rate = (completed_calls / total_calls) * 100 if total_calls > 0 else 0
        
        total_duration = sum([
            c.get("end_time", c["start_time"]) - c["start_time"] 
            for c in calls if c.get("end_time")
        ])
        avg_duration = total_duration / max(1, len([c for c in calls if c.get("end_time")]))
        
        all_ttft = []
        all_user_latencies = []
        total_llm_calls = 0
        
        for call in calls:
            if call.get("llm_ttft_times"):
                all_ttft.extend(call["llm_ttft_times"])
            if call.get("user_latencies"):
                all_user_latencies.extend(call["user_latencies"])
            total_llm_calls += call.get("llm_calls", 0)
        
        avg_ttft = sum(all_ttft) / len(all_ttft) if all_ttft else 0
        avg_user_latency = sum(all_user_latencies) / len(all_user_latencies) if all_user_latencies else 0
        
        return {
            "total_calls": total_calls,
            "completed_calls": completed_calls,
            "success_rate": round(success_rate, 2),
            "performance_summary": {
                "avg_call_duration_seconds": round(avg_duration, 2),
                "avg_llm_ttft_seconds": round(avg_ttft, 3),
                "avg_user_latency_seconds": round(avg_user_latency, 3),
                "total_llm_calls": total_llm_calls,
                "calls_per_hour": round(total_calls / max(1, avg_duration / 3600), 1)
            },
            "recent_calls": calls[-10:] if len(calls) > 10 else calls,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Customized dashboard"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LiveKit Load Test Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .header {{ background: #007bff; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .metric {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
            .status-good {{ color: #28a745; font-weight: bold; }}
            .status-warning {{ color: #ffc107; font-weight: bold; }}
            .status-critical {{ color: #dc3545; font-weight: bold; }}
            .refresh-btn {{ background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 10px 5px; }}
            .call-item {{ padding: 8px; margin: 5px 0; background: #f8f9fa; border-radius: 4px; }}
            h1, h2 {{ color: #333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 LiveKit Load Test Dashboard</h1>
                <p>Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db} | Target: 500 calls in 3 hours</p>
            </div>
            
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
            <button class="refresh-btn" onclick="window.open('/docs', '_blank')">📋 API Docs</button>
            
            <div class="card">
                <h2>📊 System Status</h2>
                <div id="system-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>📞 Active Calls (Real-time)</h2>
                <div id="active-calls">Loading...</div>
            </div>
            
            <div class="card">
                <h2>📈 Load Test Progress</h2>
                <div id="performance">Loading...</div>
            </div>
        </div>

        <script>
            async function fetchData(endpoint) {{
                try {{
                    const response = await fetch('/api' + endpoint);
                    return await response.json();
                }} catch (error) {{
                    console.error('Fetch error:', error);
                    return null;
                }}
            }}

            async function updateSystemStatus() {{
                const data = await fetchData('/status');
                if (!data) return;

                let statusClass = 'status-good';
                let statusText = 'Healthy';
                
                if (data.system_metrics && data.system_metrics.cpu_percent > 75) {{
                    statusClass = 'status-warning';
                    statusText = 'High CPU';
                }}

                const utilizationColor = data.utilization_percent > 80 ? 'status-warning' : 'status-good';

                document.getElementById('system-status').innerHTML = 
                    '<div class="metric"><span>Agent:</span><span>' + data.agent_name + '</span></div>' +
                    '<div class="metric"><span>Status:</span><span class="' + statusClass + '">' + statusText + '</span></div>' +
                    '<div class="metric"><span>Active Calls:</span><span class="' + utilizationColor + '">' + data.active_calls + '/' + data.max_concurrent + '</span></div>' +
                    '<div class="metric"><span>Utilization:</span><span class="' + utilizationColor + '">' + data.utilization_percent + '%</span></div>' +
                    '<div class="metric"><span>Redis:</span><span>' + data.redis_info + '</span></div>' +
                    (data.system_metrics ? 
                        '<div class="metric"><span>CPU:</span><span>' + data.system_metrics.cpu_percent.toFixed(1) + '%</span></div>' +
                        '<div class="metric"><span>Memory:</span><span>' + data.system_metrics.memory_percent.toFixed(1) + '%</span></div>' +
                        '<div class="metric"><span>Uptime:</span><span>' + Math.floor(data.system_metrics.uptime_seconds / 60) + ' min</span></div>'
                        : '');
            }}

            async function updateActiveCalls() {{
                const data = await fetchData('/status');
                if (!data) return;

                let html = '<div><strong>Total Active: ' + data.active_calls + '</strong></div>';
                
                if (data.active_call_details && data.active_call_details.length > 0) {{
                    data.active_call_details.forEach(call => {{
                        const minutes = Math.floor(call.duration_seconds / 60);
                        const seconds = Math.floor(call.duration_seconds % 60);
                        html += '<div class="call-item"><strong>' + call.room_name + '</strong> (' + 
                                minutes + 'm ' + seconds + 's) - LLM: ' + call.llm_calls + 
                                (call.phone_number ? ' - ' + call.phone_number : '') + '</div>';
                    }});
                }} else if (data.active_calls === 0) {{
                    html += '<div class="call-item">🟢 No active calls - Ready for load test</div>';
                }}
                
                document.getElementById('active-calls').innerHTML = html;
            }}

            async function updatePerformance() {{
                const data = await fetchData('/performance');
                if (!data) return;

                const perf = data.performance_summary;
                const progress = (data.total_calls / 500) * 100;
                const progressColor = progress > 80 ? 'status-good' : progress > 50 ? 'status-warning' : 'status-critical';
                
                document.getElementById('performance').innerHTML = 
                    '<div class="metric"><span>Progress:</span><span class="' + progressColor + '">' + data.total_calls + '/500 calls (' + progress.toFixed(1) + '%)</span></div>' +
                    '<div class="metric"><span>Success Rate:</span><span>' + data.success_rate + '%</span></div>' +
                    (perf ? 
                        '<div class="metric"><span>Avg Duration:</span><span>' + perf.avg_call_duration_seconds + 's</span></div>' +
                        '<div class="metric"><span>Avg LLM TTFT:</span><span>' + perf.avg_llm_ttft_seconds + 's</span></div>' +
                        '<div class="metric"><span>Calls/Hour Rate:</span><span>' + perf.calls_per_hour + '</span></div>' +
                        '<div class="metric"><span>ETA (at current rate):</span><span>' + ((500 - data.total_calls) / Math.max(1, perf.calls_per_hour)).toFixed(1) + ' hours</span></div>'
                        : '<div class="metric"><span>No completed calls yet</span></div>');
            }}

            async function refreshData() {{
                await Promise.all([updateSystemStatus(), updateActiveCalls(), updatePerformance()]);
            }}

            refreshData();
            setInterval(refreshData, 10000); // Refresh every 10 seconds
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    
    port = config.monitoring_port
    
    print(f"🚀 Starting Monitoring API on port {port}")
    print(f"📊 Dashboard: http://localhost:{port}")
    print(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    
    uvicorn.run(app, host=config.monitoring_host, port=port)
EOF

# 5. Create test scripts
echo "📝 Creating test scripts..."

cat > test_metrics.py << 'EOF'
#!/usr/bin/env python3
"""Quick test script - CUSTOMIZED"""

import asyncio
import time
import sys
import os
sys.path.append('.')

from config.metrics_config import get_metrics_config
from metrics.simple_recorder import initialize_simple_metrics, get_simple_recorder

async def test_metrics():
    print("🧪 Testing metrics system...")
    print("🔧 Using your Redis: sbi.vaaniresearch.com:6379/db15")
    
    # Initialize
    await initialize_simple_metrics("test-agent")
    recorder = get_simple_recorder()
    
    # Start a test call
    call_id = await recorder.start_call("test-room-123", "+1234567890")
    print(f"✅ Started test call: {call_id}")
    
    # Simulate some metrics
    await recorder.record_llm_metric(call_id, 0.5)
    await recorder.record_asr_metric(call_id)
    await recorder.record_tts_metric(call_id)
    await recorder.record_user_latency(call_id, 1.2)
    
    print("✅ Recorded test metrics")
    
    # Get live stats
    stats = await recorder.get_live_stats()
    print(f"📊 Live stats: {stats}")
    
    # End call
    await recorder.end_call(call_id, "completed")
    print("✅ Test completed")
    
    await recorder.cleanup()

if __name__ == "__main__":
    asyncio.run(test_metrics())
EOF

cat > start_monitoring.py << 'EOF'
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
EOF

cat > tools/load_test_monitor.py << 'EOF'
#!/usr/bin/env python3
"""Load test monitoring - CUSTOMIZED for your setup"""

import asyncio
import aiohttp
import time
from datetime import datetime

async def monitor_load_test(duration_hours=3, target_calls=500):
    """Monitor system during load test"""
    
    print(f"🎯 Load Test Monitor Started")
    print(f"   Target: {target_calls} calls in {duration_hours} hours")
    print(f"   Rate needed: {target_calls/duration_hours:.1f} calls/hour")
    print(f"   Dashboard: http://localhost:1234")
    print(f"   Redis: sbi.vaaniresearch.com:6379/db15")
    print("")
    
    start_time = time.time()
    end_time = start_time + (duration_hours * 3600)
    
    session = aiohttp.ClientSession()
    
    try:
        while time.time() < end_time:
            try:
                # CUSTOMIZED: Use your port
                async with session.get("http://localhost:1234/api/status") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        elapsed_hours = (time.time() - start_time) / 3600
                        
                        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} | "
                              f"Active: {data['active_calls']}/{data['max_concurrent']} | "
                              f"Utilization: {data['utilization_percent']:.1f}% | "
                              f"Elapsed: {elapsed_hours:.1f}h")
                        
                        if data.get('system_metrics'):
                            sys_metrics = data['system_metrics']
                            cpu = sys_metrics.get('cpu_percent', 0)
                            mem = sys_metrics.get('memory_percent', 0)
                            
                            if cpu > 80 or mem > 80:
                                print(f"⚠️  HIGH USAGE: CPU {cpu:.1f}%, Memory {mem:.1f}%")
                
                async with session.get("http://localhost:1234/api/performance") as resp:
                    if resp.status == 200:
                        perf_data = await resp.json()
                        
                        if perf_data['total_calls'] > 0:
                            calls_per_hour = perf_data['total_calls'] / max(0.1, elapsed_hours)
                            eta_hours = (target_calls - perf_data['total_calls']) / max(1, calls_per_hour)
                            
                            print(f"📈 Progress: {perf_data['total_calls']}/{target_calls} calls "
                                  f"({(perf_data['total_calls']/target_calls)*100:.1f}%) | "
                                  f"Rate: {calls_per_hour:.1f}/hour | "
                                  f"ETA: {eta_hours:.1f}h | "
                                  f"Success: {perf_data['success_rate']:.1f}%")
                            
                            perf = perf_data.get('performance_summary', {})
                            if perf:
                                print(f"🎯 Performance: LLM {perf.get('avg_llm_ttft_seconds', 0):.3f}s, "
                                      f"User {perf.get('avg_user_latency_seconds', 0):.3f}s, "
                                      f"Duration {perf.get('avg_call_duration_seconds', 0):.1f}s")
                        
                        print("-" * 80)
            
            except Exception as e:
                print(f"❌ Monitor error: {e}")
            
            await asyncio.sleep(30)
    
    finally:
        await session.close()
        print("🏁 Load test monitoring completed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor load test")
    parser.add_argument("--hours", type=float, default=3, help="Test duration in hours")
    parser.add_argument("--calls", type=int, default=500, help="Target number of calls")
    
    args = parser.parse_args()
    asyncio.run(monitor_load_test(args.hours, args.calls))
EOF

# 6. Update .env.local
echo "📝 Updating .env.local..."
cat >> .env.local << 'EOF'

# CUSTOMIZED Metrics Configuration
METRICS_ENABLED=true
AGENT_NAME=outbound-caller
REDIS_HOST=sbi.vaaniresearch.com
REDIS_PORT=6379
REDIS_DB=15
MONITORING_PORT=1234
MAX_CONCURRENT_CALLS=50
TARGET_CALLS_FOR_TEST=500

EOF

# Make scripts executable
chmod +x test_metrics.py
chmod +x start_monitoring.py
chmod +x tools/load_test_monitor.py

echo ""
echo "🎉 CUSTOMIZED SETUP COMPLETE!"
echo ""
echo "✅ Customizations applied:"
echo "   🔧 Redis: sbi.vaaniresearch.com:6379/db15 (avoids conflicts)"
echo "   🌐 Monitoring: Port 1234 (your available port)"
echo "   🔑 Prefixed keys: 'livekit_metrics:*' (won't interfere with pub-sub)"
echo ""
echo "🚀 QUICK START:"
echo "1️⃣ Test Redis connection:"
echo "   python3 test_metrics.py"
echo ""
echo "2️⃣ Start dashboard:"
echo "   python3 start_monitoring.py &"
echo "   # Opens at http://localhost:1234"