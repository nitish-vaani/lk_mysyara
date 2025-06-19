#!/usr/bin/env python3
# quick_diagnostics.py - Check why no metrics are being stored

import sys
import os
sys.path.append('.')

print("🔍 DIAGNOSING METRICS SYSTEM")
print("="*50)

# 1. Check if modules can be imported
print("1️⃣ CHECKING IMPORTS:")
try:
    from config.metrics_config import get_metrics_config
    print("   ✅ Config module imported")
    
    config = get_metrics_config()
    print(f"   ✅ Config loaded: enabled={config.enabled}")
    print(f"   🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    print(f"   📊 Agent: {config.agent_name}")
    print(f"   📈 Port: {config.monitoring_port}")
    
except Exception as e:
    print(f"   ❌ Config import failed: {e}")
    exit(1)

try:
    from metrics.simple_recorder import get_simple_recorder, initialize_simple_metrics
    print("   ✅ Metrics recorder imported")
except Exception as e:
    print(f"   ❌ Metrics recorder import failed: {e}")
    exit(1)

print()

# 2. Check Redis connection
print("2️⃣ CHECKING REDIS CONNECTION:")
import asyncio
import redis.asyncio as redis

async def test_redis():
    try:
        redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True
        )
        await redis_client.ping()
        print("   ✅ Redis connection works")
        
        # Test write/read
        test_key = "livekit_metrics:test_key"
        await redis_client.set(test_key, "test_value", ex=60)
        value = await redis_client.get(test_key)
        if value == "test_value":
            print("   ✅ Redis read/write works")
            await redis_client.delete(test_key)
        else:
            print("   ❌ Redis read/write failed")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        return False
    return True

redis_works = asyncio.run(test_redis())
if not redis_works:
    exit(1)

print()

# 3. Test metrics initialization
print("3️⃣ TESTING METRICS INITIALIZATION:")

async def test_metrics_init():
    try:
        await initialize_simple_metrics("diagnostic-agent")
        print("   ✅ Metrics initialization successful")
        
        recorder = get_simple_recorder()
        print("   ✅ Metrics recorder available")
        
        # Test a simple recording
        call_id = await recorder.start_call("diagnostic-room", "+1234567890")
        print(f"   ✅ Test call started: {call_id}")
        
        await recorder.record_llm_metric(call_id, 0.5)
        await recorder.record_tts_metric(call_id)
        await recorder.record_asr_metric(call_id)
        print("   ✅ Test metrics recorded")
        
        # Check if stored
        stats = await recorder.get_live_stats()
        print(f"   📊 Live stats: {stats}")
        
        await recorder.end_call(call_id, "completed")
        print("   ✅ Test call completed")
        
        await recorder.cleanup()
        return True
        
    except Exception as e:
        print(f"   ❌ Metrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

metrics_works = asyncio.run(test_metrics_init())

print()

# 4. Check for data after test
print("4️⃣ CHECKING IF TEST DATA WAS STORED:")

async def check_test_data():
    try:
        redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True
        )
        
        # Check for any livekit_metrics keys
        keys = await redis_client.keys("livekit_metrics:*")
        print(f"   📋 Found {len(keys)} livekit_metrics keys")
        
        for key in keys[:5]:  # Show first 5
            print(f"      🔑 {key}")
        
        # Check completed calls
        completed = await redis_client.lrange("livekit_metrics:completed_calls", 0, -1)
        print(f"   ✅ Found {len(completed)} completed calls")
        
        if completed:
            import json
            call = json.loads(completed[0])
            print(f"      📞 Latest call: {call['call_id']}")
            print(f"      📊 LLM calls: {call.get('llm_calls', 0)}")
            print(f"      📊 TTS calls: {call.get('tts_calls', 0)}")
            print(f"      📊 ASR calls: {call.get('asr_calls', 0)}")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"   ❌ Data check failed: {e}")

asyncio.run(check_test_data())

print()

# 5. Final diagnosis
print("5️⃣ DIAGNOSIS:")
print("   📋 If you see test data above, metrics system is working!")
print("   📋 If no test data, there's an issue with Redis/storage")
print("   📋 To get real metrics, you need to:")
print("      1. Use the enhanced agent.py code")
print("      2. Make real calls through your agent") 
print("      3. System metrics need background monitoring running")
print()
print("🔧 NEXT STEPS:")
print("   1. Check if your agent.py has the enhanced code")
print("   2. Start your agent and make a test call")
print("   3. Run: python3 debug_metrics.py again")
print()
print("📞 SYSTEM METRICS NOTE:")
print("   System metrics (CPU, Memory) only appear when:")
print("   - Agent is running with metrics enabled")
print("   - Background monitoring task is active")
print("   - Agent has been running for > 60 seconds")