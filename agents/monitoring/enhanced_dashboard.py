from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import redis.asyncio as redis
from datetime import datetime
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.enhanced_metrics_config import EnhancedMetricsConfig

logger = logging.getLogger("enhanced_dashboard")

app = FastAPI(
    title="Enhanced LiveKit Load Testing Dashboard",
    description="Advanced metrics and load testing monitoring",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration
config = EnhancedMetricsConfig.from_yaml()
redis_client = None

# Mount static files (HTML, CSS, JS)
html_directory = os.path.join(os.path.dirname(__file__), '..', 'html')
app.mount("/static", StaticFiles(directory=html_directory), name="static")

@app.on_event("startup")
async def startup():
    global redis_client
    try:
        redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"✅ Enhanced dashboard connected to Redis")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()

# ==============================================================================
# HTML ROUTES - Serve HTML files from /agents/html folder
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def main_dashboard():
    """Serve the main dashboard HTML file"""
    html_file = os.path.join(html_directory, "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        raise HTTPException(status_code=404, detail="Main dashboard HTML not found")

@app.get("/calls", response_class=HTMLResponse)
async def calls_dashboard():
    """Serve the call-by-call metrics HTML file"""
    html_file = os.path.join(html_directory, "calls.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        raise HTTPException(status_code=404, detail="Call metrics dashboard HTML not found")

# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/enhanced-status")
async def get_enhanced_status():
    """Get enhanced system status with detailed load testing metrics"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Get all enhanced metrics
        call_keys = await redis_client.keys("enhanced_metrics:call:*")
        active_calls = []
        total_calls = 0
        
        for key in call_keys:
            call_data = await redis_client.get(key)
            if call_data:
                call = json.loads(call_data)
                total_calls += 1
                
                if call.get("status") == "active":
                    current_time = datetime.now().timestamp()
                    duration = current_time - call["start_time"]
                    
                    # Calculate real-time metrics
                    llm_calls = len(call.get('llm_metrics', []))
                    tts_calls = len(call.get('tts_metrics', []))
                    asr_calls = len(call.get('asr_metrics', []))
                    
                    # Calculate average latencies
                    llm_metrics = call.get('llm_metrics', [])
                    avg_ttft = sum(m['ttft'] for m in llm_metrics) / max(1, len(llm_metrics))
                    
                    user_latencies = call.get('user_latency_metrics', [])
                    avg_user_latency = sum(m['latency'] for m in user_latencies) / max(1, len(user_latencies))
                    
                    active_calls.append({
                        "call_id": call["call_id"],
                        "client_name": call["client_name"],
                        "phone_number": call.get("phone_number", ""),
                        "duration_seconds": round(duration, 1),
                        "duration_minutes": round(duration / 60, 2),
                        "llm_calls": llm_calls,
                        "tts_calls": tts_calls,
                        "asr_calls": asr_calls,
                        "avg_ttft": round(avg_ttft, 3),
                        "avg_user_latency": round(avg_user_latency, 3),
                        "interactions_per_minute": round((llm_calls + tts_calls) / max(1, duration/60), 1),
                        "status_health": "healthy" if avg_ttft < 2.0 and duration < 600 else "warning"
                    })
        
        # Get completed calls for statistics
        completed_data = await redis_client.lrange("enhanced_metrics:completed_calls", 0, -1)
        completed_calls = []
        
        if completed_data:
            for call_json in completed_data[-50:]:  # Last 50 calls
                call = json.loads(call_json)
                completed_calls.append(call)
        
        # Calculate aggregate statistics
        total_active = len(active_calls)
        total_completed = len(completed_calls)
        
        # Performance stats from completed calls
        if completed_calls:
            successful_calls = [c for c in completed_calls if c.get('status') == 'completed']
            success_rate = (len(successful_calls) / len(completed_calls)) * 100
            
            # Calculate averages
            avg_duration = sum((c.get('end_time', c['start_time']) - c['start_time']) for c in successful_calls) / max(1, len(successful_calls))
            
            all_llm_metrics = []
            all_user_latencies = []
            total_interactions = 0
            
            for call in completed_calls:
                llm_metrics = call.get('llm_metrics', [])
                all_llm_metrics.extend([m['ttft'] for m in llm_metrics])
                
                user_metrics = call.get('user_latency_metrics', [])
                all_user_latencies.extend([m['latency'] for m in user_metrics])
                
                total_interactions += len(call.get('llm_metrics', [])) + len(call.get('tts_metrics', []))
            
            avg_ttft = sum(all_llm_metrics) / max(1, len(all_llm_metrics))
            avg_user_latency = sum(all_user_latencies) / max(1, len(all_user_latencies))
            
        else:
            success_rate = 0
            avg_duration = 0
            avg_ttft = 0
            avg_user_latency = 0
            total_interactions = 0
        
        return {
            "timestamp": datetime.now(),
            "load_test_status": {
                "active_calls": total_active,
                "total_calls_processed": total_completed,
                "max_concurrent": config.load_test.max_concurrent_calls,
                "utilization_percent": round((total_active / config.load_test.max_concurrent_calls) * 100, 1),
                "target_calls": config.load_test.initial_concurrent_calls,
            },
            "performance_summary": {
                "success_rate": round(success_rate, 1),
                "avg_call_duration": round(avg_duration, 1),
                "avg_ttft_seconds": round(avg_ttft, 3),
                "avg_user_latency_seconds": round(avg_user_latency, 3),
                "total_interactions": total_interactions
            },
            "active_calls": active_calls,
            "system_health": {
                "redis_connected": True,
                "enhanced_metrics_enabled": True,
                "client_name": config.client_name,
                "agent_name": config.agent_name
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get enhanced status")

@app.get("/api/load-test-analytics")
async def get_load_test_analytics():
    """Get detailed load test analytics and trends"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Get completed calls data
        completed_data = await redis_client.lrange("enhanced_metrics:completed_calls", 0, -1)
        
        if not completed_data:
            return {"message": "No load test data available"}
        
        calls = [json.loads(call) for call in completed_data]
        
        # Time-based analysis
        now = datetime.now().timestamp()
        last_hour_calls = [c for c in calls if (now - c['start_time']) < 3600]
        last_24h_calls = [c for c in calls if (now - c['start_time']) < 86400]
        
        # Performance trends
        performance_trends = {
            "hourly": {
                "total_calls": len(last_hour_calls),
                "success_rate": len([c for c in last_hour_calls if c.get('status') == 'completed']) / max(1, len(last_hour_calls)) * 100,
                "avg_ttft": 0,
                "avg_user_latency": 0
            },
            "daily": {
                "total_calls": len(last_24h_calls),
                "success_rate": len([c for c in last_24h_calls if c.get('status') == 'completed']) / max(1, len(last_24h_calls)) * 100,
                "avg_ttft": 0,
                "avg_user_latency": 0
            }
        }
        
        # Calculate performance metrics for trends
        for period, data in [("hourly", last_hour_calls), ("daily", last_24h_calls)]:
            if data:
                all_ttft = []
                all_user_latencies = []
                
                for call in data:
                    llm_metrics = call.get('llm_metrics', [])
                    all_ttft.extend([m['ttft'] for m in llm_metrics])
                    
                    user_metrics = call.get('user_latency_metrics', [])
                    all_user_latencies.extend([m['latency'] for m in user_metrics])
                
                performance_trends[period]["avg_ttft"] = round(sum(all_ttft) / max(1, len(all_ttft)), 3)
                performance_trends[period]["avg_user_latency"] = round(sum(all_user_latencies) / max(1, len(all_user_latencies)), 3)
        
        # Client breakdown
        client_stats = {}
        for call in calls:
            client = call.get('client_name', 'unknown')
            if client not in client_stats:
                client_stats[client] = {"calls": 0, "success": 0}
            
            client_stats[client]["calls"] += 1
            if call.get('status') == 'completed':
                client_stats[client]["success"] += 1
        
        # Performance distribution
        all_ttft = []
        all_user_latencies = []
        call_durations = []
        
        for call in calls:
            if call.get('end_time'):
                call_durations.append(call['end_time'] - call['start_time'])
            
            llm_metrics = call.get('llm_metrics', [])
            all_ttft.extend([m['ttft'] for m in llm_metrics])
            
            user_metrics = call.get('user_latency_metrics', [])
            all_user_latencies.extend([m['latency'] for m in user_metrics])
        
        # Performance percentiles
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            index = int(len(sorted_data) * p / 100)
            return sorted_data[min(index, len(sorted_data) - 1)]
        
        return {
            "timestamp": datetime.now(),
            "performance_trends": performance_trends,
            "client_breakdown": client_stats,
            "performance_distribution": {
                "ttft_percentiles": {
                    "p50": round(percentile(all_ttft, 50), 3),
                    "p90": round(percentile(all_ttft, 90), 3),
                    "p95": round(percentile(all_ttft, 95), 3),
                    "p99": round(percentile(all_ttft, 99), 3)
                },
                "user_latency_percentiles": {
                    "p50": round(percentile(all_user_latencies, 50), 3),
                    "p90": round(percentile(all_user_latencies, 90), 3),
                    "p95": round(percentile(all_user_latencies, 95), 3),
                    "p99": round(percentile(all_user_latencies, 99), 3)
                },
                "call_duration_percentiles": {
                    "p50": round(percentile(call_durations, 50), 1),
                    "p90": round(percentile(call_durations, 90), 1),
                    "p95": round(percentile(call_durations, 95), 1),
                    "p99": round(percentile(call_durations, 99), 1)
                }
            },
            "load_test_progress": {
                "total_calls_completed": len(calls),
                "target_calls": config.load_test.initial_concurrent_calls,
                "progress_percentage": min(100, (len(calls) / config.load_test.initial_concurrent_calls) * 100)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting load test analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get load test analytics")

@app.get("/api/calls")
async def get_all_calls():
    """Get list of all calls with basic info"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Get active calls
        active_keys = await redis_client.keys("enhanced_metrics:call:*")
        active_calls = []
        
        for key in active_keys:
            call_data = await redis_client.get(key)
            if call_data:
                call = json.loads(call_data)
                if call.get("status") == "active":
                    active_calls.append({
                        "call_id": call["call_id"],
                        "room_name": call["room_name"],
                        "phone_number": call.get("phone_number", ""),
                        "caller_name": call.get("caller_name", ""),
                        "client_name": call["client_name"],
                        "start_time": call["start_time"],
                        "status": "active",
                        "duration": datetime.now().timestamp() - call["start_time"]
                    })
        
        # Get completed calls
        completed_data = await redis_client.lrange("enhanced_metrics:completed_calls", 0, 99)  # Last 100
        completed_calls = []
        
        if completed_data:
            for call_json in completed_data:
                call = json.loads(call_json)
                completed_calls.append({
                    "call_id": call["call_id"],
                    "room_name": call["room_name"],
                    "phone_number": call.get("phone_number", ""),
                    "caller_name": call.get("caller_name", ""),
                    "client_name": call["client_name"],
                    "start_time": call["start_time"],
                    "end_time": call.get("end_time"),
                    "status": call.get("status", "completed"),
                    "duration": (call.get("end_time", call["start_time"]) - call["start_time"])
                })
        
        return {
            "active_calls": active_calls,
            "completed_calls": completed_calls,
            "total_active": len(active_calls),
            "total_completed": len(completed_calls)
        }
        
    except Exception as e:
        logger.error(f"Error getting calls: {e}")
        raise HTTPException(status_code=500, detail="Failed to get calls")

@app.get("/api/call/{call_id}")
async def get_call_details(call_id: str):
    """Get detailed metrics for a specific call"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Try to get from active calls first
        call_key = f"enhanced_metrics:call:{call_id}"
        call_data = await redis_client.get(call_key)
        
        if not call_data:
            # Try to find in completed calls
            completed_data = await redis_client.lrange("enhanced_metrics:completed_calls", 0, -1)
            for call_json in completed_data:
                call = json.loads(call_json)
                if call["call_id"] == call_id:
                    call_data = call_json
                    break
        
        if not call_data:
            raise HTTPException(status_code=404, detail="Call not found")
        
        call = json.loads(call_data)
        
        # Calculate aggregated metrics
        llm_metrics = call.get('llm_metrics', [])
        tts_metrics = call.get('tts_metrics', [])
        asr_metrics = call.get('asr_metrics', [])
        eou_metrics = call.get('eou_metrics', [])
        user_latency_metrics = call.get('user_latency_metrics', [])
        
        # Calculate averages and totals
        avg_ttft = sum(m['ttft'] for m in llm_metrics) / max(1, len(llm_metrics))
        avg_tts_ttfb = sum(m['ttfb'] for m in tts_metrics) / max(1, len(tts_metrics))
        avg_asr_duration = sum(m['duration'] for m in asr_metrics) / max(1, len(asr_metrics))
        avg_eou_delay = sum(m['delay'] for m in eou_metrics) / max(1, len(eou_metrics))
        avg_user_latency = sum(m['latency'] for m in user_latency_metrics) / max(1, len(user_latency_metrics))
        
        total_tokens_in = sum(m.get('tokens_in', 0) for m in llm_metrics)
        total_tokens_out = sum(m.get('tokens_out', 0) for m in llm_metrics)
        total_tts_duration = sum(m.get('duration', 0) for m in tts_metrics)
        total_asr_duration = sum(m.get('duration', 0) for m in asr_metrics)
        
        return {
            "call_info": {
                "call_id": call["call_id"],
                "room_name": call["room_name"],
                "phone_number": call.get("phone_number", ""),
                "caller_name": call.get("caller_name", ""),
                "client_name": call["client_name"],
                "agent_name": call["agent_name"],
                "start_time": call["start_time"],
                "end_time": call.get("end_time"),
                "status": call.get("status", "active"),
                "duration_seconds": (call.get("end_time", datetime.now().timestamp()) - call["start_time"]),
                "failure_reason": call.get("failure_reason")
            },
            "metrics_summary": {
                "llm_calls": len(llm_metrics),
                "tts_calls": len(tts_metrics),
                "asr_calls": len(asr_metrics),
                "eou_events": len(eou_metrics),
                "user_latency_events": len(user_latency_metrics),
                "total_interactions": len(llm_metrics) + len(tts_metrics),
                "avg_ttft_seconds": round(avg_ttft, 3),
                "avg_tts_ttfb_seconds": round(avg_tts_ttfb, 3),
                "avg_asr_duration_seconds": round(avg_asr_duration, 3),
                "avg_eou_delay_seconds": round(avg_eou_delay, 3),
                "avg_user_latency_seconds": round(avg_user_latency, 3),
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out,
                "total_tts_duration_seconds": round(total_tts_duration, 3),
                "total_asr_duration_seconds": round(total_asr_duration, 3)
            },
            "detailed_metrics": {
                "llm_metrics": llm_metrics,
                "tts_metrics": tts_metrics,
                "asr_metrics": asr_metrics,
                "eou_metrics": eou_metrics,
                "user_latency_metrics": user_latency_metrics
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get call details")

@app.get("/api/call/{call_id}/timeline")
async def get_call_timeline(call_id: str):
    """Get chronological timeline of all metrics for a call"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Get call details
        call_details = await get_call_details(call_id)
        detailed_metrics = call_details["detailed_metrics"]
        
        # Create timeline by combining all metrics and sorting by timestamp
        timeline = []
        
        # Add LLM metrics
        for metric in detailed_metrics["llm_metrics"]:
            timeline.append({
                "timestamp": metric["timestamp"],
                "type": "LLM",
                "event": f"LLM Response #{metric['sequence']}",
                "details": {
                    "ttft": metric["ttft"],
                    "tokens_in": metric.get("tokens_in", 0),
                    "tokens_out": metric.get("tokens_out", 0)
                }
            })
        
        # Add TTS metrics
        for metric in detailed_metrics["tts_metrics"]:
            timeline.append({
                "timestamp": metric["timestamp"],
                "type": "TTS",
                "event": f"TTS Audio #{metric['sequence']}",
                "details": {
                    "ttfb": metric.get("ttfb", 0),
                    "duration": metric.get("duration", 0),
                    "characters": metric.get("characters", 0)
                }
            })
        
        # Add ASR metrics
        for metric in detailed_metrics["asr_metrics"]:
            timeline.append({
                "timestamp": metric["timestamp"],
                "type": "ASR",
                "event": f"ASR Transcription #{metric['sequence']}",
                "details": {
                    "duration": metric.get("duration", 0),
                    "words": metric.get("words", 0)
                }
            })
        
        # Add EOU metrics
        for metric in detailed_metrics["eou_metrics"]:
            timeline.append({
                "timestamp": metric["timestamp"],
                "type": "EOU",
                "event": f"End of Utterance #{metric['sequence']}",
                "details": {
                    "delay": metric["delay"]
                }
            })
        
        # Add User Latency metrics
        for metric in detailed_metrics["user_latency_metrics"]:
            timeline.append({
                "timestamp": metric["timestamp"],
                "type": "USER_LATENCY",
                "event": f"User Latency #{metric['sequence']}",
                "details": {
                    "latency": metric["latency"]
                }
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        
        # Add relative timestamps (seconds from call start)
        call_start = call_details["call_info"]["start_time"]
        for event in timeline:
            event["relative_time"] = round(event["timestamp"] - call_start, 3)
            event["formatted_time"] = datetime.fromtimestamp(event["timestamp"]).strftime("%H:%M:%S")
        
        return {
            "call_id": call_id,
            "timeline": timeline,
            "total_events": len(timeline)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to get call timeline")

if __name__ == "__main__":
    import uvicorn
    
    port = config.monitoring_port
    
    print(f"🚀 Starting Enhanced Dashboard on port {port}")
    print(f"📊 Main Dashboard: http://localhost:{port}")
    print(f"📞 Call Metrics: http://localhost:{port}/calls")
    print(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
    print(f"📁 HTML files: {html_directory}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)