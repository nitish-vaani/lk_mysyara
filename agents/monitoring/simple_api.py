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

# Add these new endpoints to your monitoring/simple_api.py

@app.get("/api/detailed-metrics")
async def get_detailed_metrics():
    """Get detailed LLM, TTS, ASR, E2E, EOU metrics"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        # Get all completed calls for detailed analysis
        completed_data = await redis_client.lrange("livekit_metrics:completed_calls", 0, -1)
        
        if not completed_data:
            return {
                "message": "No detailed metrics available yet",
                "suggestions": [
                    "Make some test calls first",
                    "Check if agent.py has metrics integration",
                    "Verify metrics are being recorded"
                ]
            }
        
        calls = [json.loads(call) for call in completed_data]
        
        # Aggregate detailed metrics
        metrics = {
            "total_calls": len(calls),
            "llm_metrics": {
                "total_llm_calls": 0,
                "ttft_times": [],
                "avg_ttft": 0,
                "min_ttft": 0,
                "max_ttft": 0,
                "p95_ttft": 0
            },
            "tts_metrics": {
                "total_tts_calls": 0,
                "calls_per_session": 0
            },
            "asr_metrics": {
                "total_asr_calls": 0,
                "calls_per_session": 0
            },
            "user_experience": {
                "user_latencies": [],
                "avg_user_latency": 0,
                "min_user_latency": 0,
                "max_user_latency": 0,
                "p95_user_latency": 0
            },
            "call_quality": {
                "avg_call_duration": 0,
                "success_rate": 0,
                "completed_calls": 0,
                "failed_calls": 0
            },
            "recent_calls": []
        }
        
        # Process each call
        all_ttft = []
        all_user_latencies = []
        total_llm_calls = 0
        total_tts_calls = 0
        total_asr_calls = 0
        completed_calls = 0
        failed_calls = 0
        total_duration = 0
        
        for call in calls:
            # Count calls by status
            if call.get('status') == 'completed':
                completed_calls += 1
            else:
                failed_calls += 1
            
            # Duration
            if call.get('end_time'):
                duration = call['end_time'] - call['start_time']
                total_duration += duration
            
            # Aggregate counters
            total_llm_calls += call.get('llm_calls', 0)
            total_tts_calls += call.get('tts_calls', 0)
            total_asr_calls += call.get('asr_calls', 0)
            
            # Collect latency data
            if call.get('llm_ttft_times'):
                all_ttft.extend(call['llm_ttft_times'])
            
            if call.get('user_latencies'):
                all_user_latencies.extend(call['user_latencies'])
            
            # Recent calls for debugging
            if len(metrics["recent_calls"]) < 10:
                metrics["recent_calls"].append({
                    "call_id": call['call_id'],
                    "status": call['status'],
                    "duration": call.get('end_time', call['start_time']) - call['start_time'] if call.get('end_time') else None,
                    "llm_calls": call.get('llm_calls', 0),
                    "tts_calls": call.get('tts_calls', 0),
                    "asr_calls": call.get('asr_calls', 0),
                    "ttft_times": call.get('llm_ttft_times', []),
                    "user_latencies": call.get('user_latencies', [])
                })
        
        # Calculate LLM metrics
        metrics["llm_metrics"]["total_llm_calls"] = total_llm_calls
        if all_ttft:
            metrics["llm_metrics"]["ttft_times"] = all_ttft
            metrics["llm_metrics"]["avg_ttft"] = round(sum(all_ttft) / len(all_ttft), 3)
            metrics["llm_metrics"]["min_ttft"] = round(min(all_ttft), 3)
            metrics["llm_metrics"]["max_ttft"] = round(max(all_ttft), 3)
            
            # Calculate P95
            sorted_ttft = sorted(all_ttft)
            p95_index = int(len(sorted_ttft) * 0.95)
            metrics["llm_metrics"]["p95_ttft"] = round(sorted_ttft[p95_index], 3)
        
        # Calculate TTS/ASR metrics
        metrics["tts_metrics"]["total_tts_calls"] = total_tts_calls
        metrics["tts_metrics"]["calls_per_session"] = round(total_tts_calls / max(1, len(calls)), 1)
        
        metrics["asr_metrics"]["total_asr_calls"] = total_asr_calls
        metrics["asr_metrics"]["calls_per_session"] = round(total_asr_calls / max(1, len(calls)), 1)
        
        # Calculate User Experience metrics
        if all_user_latencies:
            metrics["user_experience"]["user_latencies"] = all_user_latencies
            metrics["user_experience"]["avg_user_latency"] = round(sum(all_user_latencies) / len(all_user_latencies), 3)
            metrics["user_experience"]["min_user_latency"] = round(min(all_user_latencies), 3)
            metrics["user_experience"]["max_user_latency"] = round(max(all_user_latencies), 3)
            
            # Calculate P95
            sorted_user = sorted(all_user_latencies)
            p95_index = int(len(sorted_user) * 0.95)
            metrics["user_experience"]["p95_user_latency"] = round(sorted_user[p95_index], 3)
        
        # Calculate Call Quality metrics
        metrics["call_quality"]["completed_calls"] = completed_calls
        metrics["call_quality"]["failed_calls"] = failed_calls
        metrics["call_quality"]["success_rate"] = round((completed_calls / max(1, len(calls))) * 100, 1)
        metrics["call_quality"]["avg_call_duration"] = round(total_duration / max(1, completed_calls), 1)
        
        return {
            "timestamp": datetime.now(),
            "detailed_metrics": metrics,
            "summary": {
                "calls_analyzed": len(calls),
                "has_llm_data": len(all_ttft) > 0,
                "has_user_latency_data": len(all_user_latencies) > 0,
                "avg_interactions_per_call": round((total_llm_calls + total_tts_calls + total_asr_calls) / max(1, len(calls)), 1)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get detailed metrics")

@app.get("/api/live-call-details")
async def get_live_call_details():
    """Get real-time details of currently active calls"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        call_keys = await redis_client.keys("livekit_metrics:call:*")
        active_calls = []
        
        for key in call_keys:
            call_data = await redis_client.get(key)
            if call_data:
                call = json.loads(call_data)
                if call.get("status") == "active":
                    current_time = datetime.now().timestamp()
                    duration = current_time - call["start_time"]
                    
                    # Calculate real-time performance
                    avg_ttft = 0
                    if call.get('llm_ttft_times'):
                        avg_ttft = sum(call['llm_ttft_times']) / len(call['llm_ttft_times'])
                    
                    avg_user_latency = 0
                    if call.get('user_latencies'):
                        avg_user_latency = sum(call['user_latencies']) / len(call['user_latencies'])
                    
                    active_calls.append({
                        "call_id": call["call_id"],
                        "room_name": call["room_name"],
                        "phone_number": call.get("phone_number", ""),
                        "duration_seconds": round(duration, 1),
                        "duration_minutes": round(duration / 60, 1),
                        
                        # Real-time counters
                        "llm_calls": call.get("llm_calls", 0),
                        "tts_calls": call.get("tts_calls", 0),
                        "asr_calls": call.get("asr_calls", 0),
                        
                        # Real-time performance
                        "current_avg_ttft": round(avg_ttft, 3),
                        "current_avg_user_latency": round(avg_user_latency, 3),
                        "recent_ttft_times": call.get('llm_ttft_times', [])[-5:],  # Last 5
                        "recent_user_latencies": call.get('user_latencies', [])[-5:],  # Last 5
                        
                        # Call health indicators
                        "interactions_per_minute": round((call.get("llm_calls", 0) + call.get("tts_calls", 0)) / max(1, duration/60), 1),
                        "is_healthy": duration < 1800 and avg_ttft < 2.0  # Less than 30min and good performance
                    })
        
        return {
            "timestamp": datetime.now(),
            "active_calls_count": len(active_calls),
            "active_calls": active_calls,
            "summary": {
                "total_active_interactions": sum(call["llm_calls"] + call["tts_calls"] for call in active_calls),
                "avg_call_duration_minutes": round(sum(call["duration_minutes"] for call in active_calls) / max(1, len(active_calls)), 1),
                "healthy_calls": len([call for call in active_calls if call["is_healthy"]])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting live call details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get live call details")

# Add this to the dashboard HTML (replace the existing performance card)
@app.get("/detailed", response_class=HTMLResponse)
async def detailed_dashboard():
    """Detailed metrics dashboard"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LiveKit Detailed Metrics</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ background: #007bff; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
            .metric:last-child {{ border-bottom: none; }}
            .good {{ color: #28a745; font-weight: bold; }}
            .warning {{ color: #ffc107; font-weight: bold; }}
            .critical {{ color: #dc3545; font-weight: bold; }}
            .refresh-btn {{ background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
            .call-item {{ padding: 10px; margin: 5px 0; background: #f8f9fa; border-radius: 4px; border-left: 4px solid #007bff; }}
            h1, h2 {{ color: #333; }}
            .no-data {{ color: #6c757d; font-style: italic; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 LiveKit Detailed Metrics Dashboard</h1>
                <p>LLM, TTS, ASR, E2E, EOU Performance Analysis</p>
            </div>
            
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
            <button class="refresh-btn" onclick="window.open('/', '_blank')">📊 Main Dashboard</button>
            <button class="refresh-btn" onclick="window.open('/docs', '_blank')">📋 API Docs</button>
            
            <div class="grid">
                <div class="card">
                    <h2>🧠 LLM Performance</h2>
                    <div id="llm-metrics">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>👤 User Experience</h2>
                    <div id="user-metrics">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>🎙️ ASR & TTS</h2>
                    <div id="asr-tts-metrics">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>📞 Call Quality</h2>
                    <div id="call-quality">Loading...</div>
                </div>
            </div>
            
            <div class="card">
                <h2>🔴 Live Active Calls</h2>
                <div id="live-calls">Loading...</div>
            </div>
            
            <div class="card">
                <h2>📋 Recent Call Details</h2>
                <div id="recent-calls">Loading...</div>
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

            async function updateLLMMetrics() {{
                const data = await fetchData('/detailed-metrics');
                if (!data || !data.detailed_metrics) return;

                const llm = data.detailed_metrics.llm_metrics;
                
                if (llm.total_llm_calls === 0) {{
                    document.getElementById('llm-metrics').innerHTML = '<div class="no-data">No LLM data yet. Make some calls to see metrics.</div>';
                    return;
                }}

                const ttftClass = llm.avg_ttft > 2 ? 'critical' : llm.avg_ttft > 1 ? 'warning' : 'good';
                
                document.getElementById('llm-metrics').innerHTML = 
                    '<div class="metric"><span>Total LLM Calls:</span><span>' + llm.total_llm_calls + '</span></div>' +
                    '<div class="metric"><span>Avg TTFT:</span><span class="' + ttftClass + '">' + llm.avg_ttft + 's</span></div>' +
                    '<div class="metric"><span>Min TTFT:</span><span>' + llm.min_ttft + 's</span></div>' +
                    '<div class="metric"><span>Max TTFT:</span><span>' + llm.max_ttft + 's</span></div>' +
                    '<div class="metric"><span>95th Percentile:</span><span class="' + ttftClass + '">' + llm.p95_ttft + 's</span></div>' +
                    '<div class="metric"><span>TTFT Samples:</span><span>' + llm.ttft_times.length + '</span></div>';
            }}

            async function updateUserMetrics() {{
                const data = await fetchData('/detailed-metrics');
                if (!data || !data.detailed_metrics) return;

                const user = data.detailed_metrics.user_experience;
                
                if (user.user_latencies.length === 0) {{
                    document.getElementById('user-metrics').innerHTML = '<div class="no-data">No user latency data yet.</div>';
                    return;
                }}

                const latencyClass = user.avg_user_latency > 3 ? 'critical' : user.avg_user_latency > 2 ? 'warning' : 'good';
                
                document.getElementById('user-metrics').innerHTML = 
                    '<div class="metric"><span>Avg User Latency:</span><span class="' + latencyClass + '">' + user.avg_user_latency + 's</span></div>' +
                    '<div class="metric"><span>Min Latency:</span><span>' + user.min_user_latency + 's</span></div>' +
                    '<div class="metric"><span>Max Latency:</span><span>' + user.max_user_latency + 's</span></div>' +
                    '<div class="metric"><span>95th Percentile:</span><span class="' + latencyClass + '">' + user.p95_user_latency + 's</span></div>' +
                    '<div class="metric"><span>Latency Samples:</span><span>' + user.user_latencies.length + '</span></div>';
            }}

            async function updateASRTTSMetrics() {{
                const data = await fetchData('/detailed-metrics');
                if (!data || !data.detailed_metrics) return;

                const asr = data.detailed_metrics.asr_metrics;
                const tts = data.detailed_metrics.tts_metrics;
                
                document.getElementById('asr-tts-metrics').innerHTML = 
                    '<div class="metric"><span>Total ASR Calls:</span><span>' + asr.total_asr_calls + '</span></div>' +
                    '<div class="metric"><span>ASR per Session:</span><span>' + asr.calls_per_session + '</span></div>' +
                    '<div class="metric"><span>Total TTS Calls:</span><span>' + tts.total_tts_calls + '</span></div>' +
                    '<div class="metric"><span>TTS per Session:</span><span>' + tts.calls_per_session + '</span></div>';
            }}

            async function updateCallQuality() {{
                const data = await fetchData('/detailed-metrics');
                if (!data || !data.detailed_metrics) return;

                const quality = data.detailed_metrics.call_quality;
                const successClass = quality.success_rate > 90 ? 'good' : quality.success_rate > 70 ? 'warning' : 'critical';
                
                document.getElementById('call-quality').innerHTML = 
                    '<div class="metric"><span>Success Rate:</span><span class="' + successClass + '">' + quality.success_rate + '%</span></div>' +
                    '<div class="metric"><span>Completed Calls:</span><span>' + quality.completed_calls + '</span></div>' +
                    '<div class="metric"><span>Failed Calls:</span><span>' + quality.failed_calls + '</span></div>' +
                    '<div class="metric"><span>Avg Duration:</span><span>' + quality.avg_call_duration + 's</span></div>';
            }}

            async function updateLiveCalls() {{
                const data = await fetchData('/live-call-details');
                if (!data) return;

                let html = '<div><strong>Active: ' + data.active_calls_count + '</strong></div>';
                
                if (data.active_calls && data.active_calls.length > 0) {{
                    data.active_calls.forEach(call => {{
                        const healthClass = call.is_healthy ? 'good' : 'warning';
                        html += '<div class="call-item">' +
                                '<div><strong>' + call.room_name + '</strong> (' + call.duration_minutes + ' min)</div>' +
                                '<div>Phone: ' + call.phone_number + '</div>' +
                                '<div>LLM: ' + call.llm_calls + ' | TTS: ' + call.tts_calls + ' | ASR: ' + call.asr_calls + '</div>' +
                                '<div>Avg TTFT: <span class="' + healthClass + '">' + call.current_avg_ttft + 's</span> | ' +
                                'User Latency: <span class="' + healthClass + '">' + call.current_avg_user_latency + 's</span></div>' +
                                '<div>Rate: ' + call.interactions_per_minute + ' interactions/min</div>' +
                                '</div>';
                    }});
                }} else {{
                    html += '<div class="no-data">No active calls</div>';
                }}
                
                document.getElementById('live-calls').innerHTML = html;
            }}

            async function updateRecentCalls() {{
                const data = await fetchData('/detailed-metrics');
                if (!data || !data.detailed_metrics) return;

                const recent = data.detailed_metrics.recent_calls;
                
                if (!recent || recent.length === 0) {{
                    document.getElementById('recent-calls').innerHTML = '<div class="no-data">No recent calls found</div>';
                    return;
                }}

                let html = '';
                recent.forEach((call, index) => {{
                    const statusClass = call.status === 'completed' ? 'good' : 'warning';
                    const avgTTFT = call.ttft_times.length > 0 ? (call.ttft_times.reduce((a, b) => a + b, 0) / call.ttft_times.length).toFixed(3) : 'N/A';
                    const avgUserLatency = call.user_latencies.length > 0 ? (call.user_latencies.reduce((a, b) => a + b, 0) / call.user_latencies.length).toFixed(3) : 'N/A';
                    
                    html += '<div class="call-item">' +
                            '<div><strong>Call ' + (index + 1) + ':</strong> ' + call.call_id + '</div>' +
                            '<div>Status: <span class="' + statusClass + '">' + call.status + '</span> | ' +
                            'Duration: ' + (call.duration ? call.duration.toFixed(1) + 's' : 'N/A') + '</div>' +
                            '<div>LLM: ' + call.llm_calls + ' | TTS: ' + call.tts_calls + ' | ASR: ' + call.asr_calls + '</div>' +
                            '<div>Avg TTFT: ' + avgTTFT + 's | Avg User Latency: ' + avgUserLatency + 's</div>' +
                            '<div>TTFT samples: [' + call.ttft_times.map(t => t.toFixed(3)).join(', ') + ']</div>' +
                            '<div>User latency samples: [' + call.user_latencies.map(t => t.toFixed(3)).join(', ') + ']</div>' +
                            '</div>';
                }});
                
                document.getElementById('recent-calls').innerHTML = html;
            }}

            async function refreshData() {{
                await Promise.all([
                    updateLLMMetrics(),
                    updateUserMetrics(),
                    updateASRTTSMetrics(),
                    updateCallQuality(),
                    updateLiveCalls(),
                    updateRecentCalls()
                ]);
            }}

            refreshData();
            setInterval(refreshData, 15000); // Refresh every 15 seconds
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
