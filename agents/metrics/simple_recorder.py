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
