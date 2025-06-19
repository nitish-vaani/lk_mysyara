import time
import socket
import statistics
import logging

logger = logging.getLogger("outbound-caller")

async def measure_network_latency():
    """Measure actual network latency to key services"""
    services = {
        'Deepgram': 'api.deepgram.com',
        'OpenAI': 'api.openai.com', 
        'LiveKit': 'us-east-1.livekit.cloud'
    }
    
    logger.info("🌐 Measuring network latency to US services...")
    total_latency = 0
    successful_measurements = 0
    
    for service_name, hostname in services.items():
        try:
            latencies = []
            for _ in range(3):
                start = time.time()
                socket.create_connection((hostname, 443), timeout=5)
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            avg_latency = statistics.mean(latencies)
            total_latency += avg_latency
            successful_measurements += 1
            logger.info(f"  {service_name}: {avg_latency:.0f}ms")
            
        except Exception as e:
            logger.warning(f"  {service_name}: Failed to measure ({e})")
    
    if successful_measurements > 0:
        avg_network_latency = total_latency / successful_measurements
        logger.info(f"📡 Average network latency: {avg_network_latency:.0f}ms")
        return avg_network_latency
    
    return 180  # Fallback to typical India-US latency