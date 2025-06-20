import sys
import os
import asyncio
sys.path.append('.')

from config.enhanced_metrics_config import EnhancedMetricsConfig
from metrics.enhanced_recorder import EnhancedMetricsRecorder

async def test_recorder():
    print("🧪 Testing Enhanced Metrics Recorder...")
    
    # Load config
    config = EnhancedMetricsConfig.from_yaml()
    print(f"✅ Config loaded for client: {config.client_name}")
    
    # Initialize recorder
    recorder = EnhancedMetricsRecorder(config)
    await recorder.initialize()
    
    # Test call tracking
    call_id = await recorder.start_call(
        room_name="test_room_123",
        phone_number="+1234567890",
        caller_name="Test User",
        client_name="test_client"
    )
    print(f"✅ Started tracking call: {call_id}")
    
    # Test metrics recording
    await recorder.record_detailed_llm_metric(call_id, ttft=0.5, tokens_in=100, tokens_out=50)
    await recorder.record_detailed_tts_metric(call_id, ttfb=0.3, duration=2.1, characters=150)
    await recorder.record_detailed_asr_metric(call_id, duration=3.2, words=25)
    await recorder.record_detailed_eou_metric(call_id, delay=0.8)
    await recorder.record_detailed_user_latency(call_id, latency=1.2)
    print("✅ Recorded test metrics")
    
    # Check active calls
    active_calls = await recorder.get_active_calls()
    print(f"✅ Active calls: {active_calls['total_active']}")
    
    # End call
    await recorder.end_call(call_id, status="completed")
    print("✅ Call ended successfully")
    
    # Cleanup
    await recorder.cleanup()
    print("✅ Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_recorder())
