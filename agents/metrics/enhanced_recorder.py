import asyncio
import json
import time
import logging
import redis.asyncio as redis
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("enhanced_metrics")

@dataclass
class DetailedCallMetrics:
    """Enhanced call metrics with detailed tracking"""
    call_id: str
    room_name: str
    agent_name: str
    client_name: str
    start_time: float
    phone_number: str = ""
    caller_name: str = ""
    
    # Status tracking
    status: str = "active"
    end_time: Optional[float] = None
    failure_reason: Optional[str] = None
    
    # Component metrics with timestamps
    llm_metrics: List[Dict] = None
    tts_metrics: List[Dict] = None
    asr_metrics: List[Dict] = None
    eou_metrics: List[Dict] = None
    user_latency_metrics: List[Dict] = None
    
    # Counters
    llm_calls: int = 0
    tts_calls: int = 0
    asr_calls: int = 0
    
    def __post_init__(self):
        if self.llm_metrics is None:
            self.llm_metrics = []
        if self.tts_metrics is None:
            self.tts_metrics = []
        if self.asr_metrics is None:
            self.asr_metrics = []
        if self.eou_metrics is None:
            self.eou_metrics = []
        if self.user_latency_metrics is None:
            self.user_latency_metrics = []
    
    def add_llm_metric(self, ttft: float, tokens_in: int = 0, tokens_out: int = 0):
        """Add LLM metric with timestamp"""
        self.llm_calls += 1
        self.llm_metrics.append({
            'timestamp': time.time(),
            'ttft': ttft,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'sequence': self.llm_calls
        })
    
    def add_tts_metric(self, ttfb: float = 0, duration: float = 0, characters: int = 0):
        """Add TTS metric with timestamp"""
        self.tts_calls += 1
        self.tts_metrics.append({
            'timestamp': time.time(),
            'ttfb': ttfb,
            'duration': duration,
            'characters': characters,
            'sequence': self.tts_calls
        })
    
    def add_asr_metric(self, duration: float = 0, words: int = 0):
        """Add ASR metric with timestamp"""
        self.asr_calls += 1
        self.asr_metrics.append({
            'timestamp': time.time(),
            'duration': duration,
            'words': words,
            'sequence': self.asr_calls
        })
    
    def add_eou_metric(self, delay: float):
        """Add End of Utterance metric"""
        self.eou_metrics.append({
            'timestamp': time.time(),
            'delay': delay,
            'sequence': len(self.eou_metrics) + 1
        })
    
    def add_user_latency_metric(self, latency: float):
        """Add user-experienced latency metric"""
        self.user_latency_metrics.append({
            'timestamp': time.time(),
            'latency': latency,
            'sequence': len(self.user_latency_metrics) + 1
        })
    
    def get_call_duration(self) -> float:
        """Get call duration in seconds"""
        end = self.end_time or time.time()
        return end - self.start_time

class EnhancedMetricsRecorder:
    """Enhanced metrics recorder with detailed tracking"""
    
    def __init__(self, config):
        self.config = config
        self.redis_client = None
        self.active_calls: Dict[str, DetailedCallMetrics] = {}
        self.start_time = time.time()
        
        logger.setLevel(logging.INFO)
        
        if self.config.enabled:
            logger.info(f"🎯 Enhanced metrics recorder initialized")
            logger.info(f"🔧 Redis: {self.config.redis_host}:{self.config.redis_port}/db{self.config.redis_db}")
            logger.info(f"👤 Client: {self.config.client_name}")
    
    async def initialize(self):
        """Initialize Redis connection"""
        if not self.config.enabled:
            return
        
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info(f"✅ Enhanced Redis connection established")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize enhanced metrics: {e}")
            logger.warning("⚠️ Continuing without enhanced metrics")
    
    async def start_call(self, room_name: str, phone_number: str = "", caller_name: str = "", client_name: str = None) -> str:
        """Start tracking a call with enhanced details"""
        if not self.config.enabled:
            return f"disabled_{room_name}"
        
        call_id = f"{room_name}_{int(time.time())}"
        client = client_name or self.config.client_name
        
        call_metrics = DetailedCallMetrics(
            call_id=call_id,
            room_name=room_name,
            agent_name=self.config.agent_name,
            client_name=client,
            start_time=time.time(),
            phone_number=phone_number,
            caller_name=caller_name
        )
        
        self.active_calls[call_id] = call_metrics
        await self._store_call_detailed(call_id, call_metrics)
        
        logger.info(f"📞 Started enhanced tracking: {call_id} (client: {client})")
        return call_id
    
    async def end_call(self, call_id: str, status: str = "completed", failure_reason: str = None):
        """End call tracking with detailed status"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.end_time = time.time()
        call_metrics.status = status
        call_metrics.failure_reason = failure_reason
        
        # Store final metrics
        await self._store_call_detailed(call_id, call_metrics)
        await self._store_completed_call_detailed(call_id, call_metrics)
        
        duration = call_metrics.get_call_duration()
        logger.info(f"📞 Enhanced call ended: {call_id} (status: {status}, duration: {duration:.1f}s)")
        
        # Clean up from active calls
        del self.active_calls[call_id]
    
    async def record_detailed_llm_metric(self, call_id: str, ttft: float, tokens_in: int = 0, tokens_out: int = 0):
        """Record detailed LLM metrics"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.add_llm_metric(ttft, tokens_in, tokens_out)
        
        logger.debug(f"🧠 Enhanced LLM metric: {call_id} - TTFT: {ttft:.3f}s, Tokens: {tokens_in}/{tokens_out}")
    
    async def record_detailed_tts_metric(self, call_id: str, ttfb: float = 0, duration: float = 0, characters: int = 0):
        """Record detailed TTS metrics"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.add_tts_metric(ttfb, duration, characters)
        
        logger.debug(f"🗣️ Enhanced TTS metric: {call_id} - TTFB: {ttfb:.3f}s, Duration: {duration:.3f}s")
    
    async def record_detailed_asr_metric(self, call_id: str, duration: float = 0, words: int = 0):
        """Record detailed ASR metrics"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.add_asr_metric(duration, words)
        
        logger.debug(f"🎤 Enhanced ASR metric: {call_id} - Duration: {duration:.3f}s, Words: {words}")
    
    async def record_detailed_eou_metric(self, call_id: str, delay: float):
        """Record detailed EOU metrics"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.add_eou_metric(delay)
        
        logger.debug(f"⏱️ Enhanced EOU metric: {call_id} - Delay: {delay:.3f}s")
    
    async def record_detailed_user_latency(self, call_id: str, latency: float):
        """Record detailed user latency metrics"""
        if call_id.startswith("disabled_") or call_id not in self.active_calls:
            return
        
        call_metrics = self.active_calls[call_id]
        call_metrics.add_user_latency_metric(latency)
        
        logger.info(f"👤 Enhanced user latency: {call_id} - Latency: {latency:.3f}s")
    
    async def get_active_calls(self) -> Dict:
        """Get current active calls for monitoring"""
        return {
            "total_active": len(self.active_calls),
            "calls": [
                {
                    "call_id": call.call_id,
                    "client_name": call.client_name,
                    "phone_number": call.phone_number,
                    "duration": call.get_call_duration(),
                    "llm_calls": call.llm_calls,
                    "tts_calls": call.tts_calls,
                    "asr_calls": call.asr_calls
                }
                for call in self.active_calls.values()
            ]
        }
    
    async def _store_call_detailed(self, call_id: str, metrics: DetailedCallMetrics):
        """Store detailed call metrics in Redis"""
        if not self.redis_client:
            return
        
        try:
            key = f"enhanced_metrics:call:{call_id}"
            data = json.dumps(asdict(metrics), default=str)
            ttl = 7 * 24 * 3600  # 7 days
            await self.redis_client.setex(key, ttl, data)
        except Exception as e:
            logger.warning(f"Failed to store detailed call metrics: {e}")
    
    async def _store_completed_call_detailed(self, call_id: str, metrics: DetailedCallMetrics):
        """Store completed call in enhanced completed calls list"""
        if not self.redis_client:
            return
        
        try:
            key = "enhanced_metrics:completed_calls"
            data = json.dumps(asdict(metrics), default=str)
            await self.redis_client.lpush(key, data)
            await self.redis_client.ltrim(key, 0, 9999)  # Keep last 10k calls
            await self.redis_client.expire(key, 30 * 24 * 3600)  # 30 days
        except Exception as e:
            logger.warning(f"Failed to store completed call: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("🧹 Enhanced metrics recorder cleaned up")