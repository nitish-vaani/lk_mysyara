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
