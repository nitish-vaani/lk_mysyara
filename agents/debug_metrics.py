#!/usr/bin/env python3
# debug_metrics.py - Tool to view all our stored metrics

import asyncio
import json
import redis.asyncio as redis
import sys
import os
sys.path.append('.')

from config.metrics_config import get_metrics_config

async def debug_all_metrics():
    """Debug tool to see all metrics in Redis"""
    
    config = get_metrics_config()
    
    print(f"🔧 Connecting to Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    
    # Connect to Redis
    redis_client = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    try:
        await redis_client.ping()
        print("✅ Redis connection successful")
        print("="*60)
        
        # 1. Check System Metrics
        print("📊 SYSTEM METRICS:")
        system_key = f"livekit_metrics:system:{config.agent_name}"
        system_data = await redis_client.get(system_key)
        
        if system_data:
            system_metrics = json.loads(system_data)
            print(f"   Agent: {system_metrics['agent_name']}")
            print(f"   CPU: {system_metrics['cpu_percent']:.1f}%")
            print(f"   Memory: {system_metrics['memory_percent']:.1f}%")
            print(f"   Active Calls: {system_metrics['active_calls']}")
            print(f"   Uptime: {system_metrics['uptime_seconds']/60:.1f} minutes")
        else:
            print("   ❌ No system metrics found")
        
        print("\n" + "="*60)
        
        # 2. Check Active Calls
        print("📞 ACTIVE CALLS:")
        call_keys = await redis_client.keys("livekit_metrics:call:*")
        
        if call_keys:
            print(f"   Found {len(call_keys)} call records")
            
            for i, key in enumerate(call_keys[:5]):  # Show first 5
                call_data = await redis_client.get(key)
                if call_data:
                    call = json.loads(call_data)
                    print(f"   Call {i+1}: {call['call_id']}")
                    print(f"      Room: {call['room_name']}")
                    print(f"      Status: {call['status']}")
                    print(f"      Phone: {call.get('phone_number', 'N/A')}")
                    print(f"      LLM Calls: {call['llm_calls']}")
                    print(f"      TTS Calls: {call['tts_calls']}")
                    print(f"      ASR Calls: {call['asr_calls']}")
                    print(f"      LLM TTFT Times: {call['llm_ttft_times']}")
                    print(f"      User Latencies: {call['user_latencies']}")
                    print(f"      Duration: {(call.get('end_time', call['start_time']) - call['start_time']):.1f}s")
                    print()
            
            if len(call_keys) > 5:
                print(f"   ... and {len(call_keys) - 5} more calls")
        else:
            print("   ❌ No active calls found")
        
        print("\n" + "="*60)
        
        # 3. Check Completed Calls
        print("✅ COMPLETED CALLS:")
        completed_data = await redis_client.lrange("livekit_metrics:completed_calls", 0, -1)
        
        if completed_data:
            print(f"   Found {len(completed_data)} completed calls")
            
            # Parse and analyze
            calls = [json.loads(call) for call in completed_data]
            
            # Show recent calls with detailed metrics
            recent_calls = calls[-5:] if len(calls) > 5 else calls
            
            for i, call in enumerate(recent_calls):
                print(f"   Call {i+1}: {call['call_id']}")
                print(f"      Status: {call['status']}")
                print(f"      Duration: {(call.get('end_time', call['start_time']) - call['start_time']):.1f}s")
                print(f"      📞 Counters:")
                print(f"         LLM Calls: {call['llm_calls']}")
                print(f"         TTS Calls: {call['tts_calls']}")
                print(f"         ASR Calls: {call['asr_calls']}")
                print(f"      ⏱️  Performance:")
                if call['llm_ttft_times']:
                    avg_ttft = sum(call['llm_ttft_times']) / len(call['llm_ttft_times'])
                    print(f"         Avg LLM TTFT: {avg_ttft:.3f}s")
                    print(f"         All TTFT: {call['llm_ttft_times']}")
                if call['user_latencies']:
                    avg_user = sum(call['user_latencies']) / len(call['user_latencies'])
                    print(f"         Avg User Latency: {avg_user:.3f}s")
                    print(f"         All User Latencies: {call['user_latencies']}")
                print()
            
            # Overall statistics
            print("📈 OVERALL STATISTICS:")
            total_calls = len(calls)
            completed_calls = len([c for c in calls if c.get('status') == 'completed'])
            success_rate = (completed_calls / total_calls) * 100 if total_calls > 0 else 0
            
            print(f"   Total Calls: {total_calls}")
            print(f"   Completed: {completed_calls}")
            print(f"   Success Rate: {success_rate:.1f}%")
            
            # Aggregate performance metrics
            all_llm_calls = sum(call['llm_calls'] for call in calls)
            all_tts_calls = sum(call['tts_calls'] for call in calls)
            all_asr_calls = sum(call['asr_calls'] for call in calls)
            
            all_ttft = []
            all_user_latencies = []
            
            for call in calls:
                all_ttft.extend(call.get('llm_ttft_times', []))
                all_user_latencies.extend(call.get('user_latencies', []))
            
            print(f"   Total LLM Calls: {all_llm_calls}")
            print(f"   Total TTS Calls: {all_tts_calls}")
            print(f"   Total ASR Calls: {all_asr_calls}")
            
            if all_ttft:
                avg_ttft = sum(all_ttft) / len(all_ttft)
                print(f"   Avg LLM TTFT: {avg_ttft:.3f}s")
                print(f"   Min/Max TTFT: {min(all_ttft):.3f}s / {max(all_ttft):.3f}s")
            
            if all_user_latencies:
                avg_user = sum(all_user_latencies) / len(all_user_latencies)
                print(f"   Avg User Latency: {avg_user:.3f}s")
                print(f"   Min/Max User Latency: {min(all_user_latencies):.3f}s / {max(all_user_latencies):.3f}s")
                
        else:
            print("   ❌ No completed calls found")
        
        print("\n" + "="*60)
        
        # 4. Redis Key Summary
        print("🔑 REDIS KEY SUMMARY:")
        all_keys = await redis_client.keys("livekit_metrics:*")
        print(f"   Total keys with 'livekit_metrics:' prefix: {len(all_keys)}")
        
        key_types = {}
        for key in all_keys:
            key_type = key.split(":")[1] if ":" in key else "unknown"
            key_types[key_type] = key_types.get(key_type, 0) + 1
        
        for key_type, count in key_types.items():
            print(f"   {key_type}: {count} keys")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await redis_client.close()

async def clear_test_data():
    """Clear test data from Redis"""
    config = get_metrics_config()
    
    redis_client = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    try:
        # Remove test calls
        test_keys = await redis_client.keys("livekit_metrics:call:test-room*")
        if test_keys:
            await redis_client.delete(*test_keys)
            print(f"🧹 Removed {len(test_keys)} test call keys")
        
        # Clean up test data from completed calls
        completed_data = await redis_client.lrange("livekit_metrics:completed_calls", 0, -1)
        if completed_data:
            calls = [json.loads(call) for call in completed_data]
            real_calls = [call for call in calls if not call['call_id'].startswith('test-room')]
            
            # Replace the list with only real calls
            await redis_client.delete("livekit_metrics:completed_calls")
            if real_calls:
                for call in real_calls:
                    await redis_client.lpush("livekit_metrics:completed_calls", json.dumps(call))
                print(f"🧹 Cleaned completed calls list, kept {len(real_calls)} real calls")
            else:
                print("🧹 Cleared all completed calls (all were test calls)")
                
    except Exception as e:
        print(f"❌ Error cleaning: {e}")
    finally:
        await redis_client.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug metrics in Redis")
    parser.add_argument("--clear-test", action="store_true", help="Clear test data")
    
    args = parser.parse_args()
    
    if args.clear_test:
        asyncio.run(clear_test_data())
    else:
        asyncio.run(debug_all_metrics())