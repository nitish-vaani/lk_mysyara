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
