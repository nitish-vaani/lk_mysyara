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
