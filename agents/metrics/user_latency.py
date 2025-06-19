import time
import statistics
import logging

logger = logging.getLogger("outbound-caller")

class UserLatencyTracker:
    """Track real user-experienced end-to-end latency"""
    
    def __init__(self):
        self.user_speech_end_times = {}
        self.ai_speech_start_times = {}
        self.user_latencies = []
        self.conversation_turn_count = 0
        
        # Network latency estimation for India-US
        self.estimated_network_overhead_ms = 216  # ~108ms each way
        
    def on_user_speech_end(self, participant_id: str):
        """Called when user stops speaking (EOU detected)"""
        timestamp = time.time()
        self.user_speech_end_times[participant_id] = timestamp
        self.conversation_turn_count += 1
        logger.debug(f"[USER LATENCY] User speech ended at {timestamp:.3f}")
        
    def on_ai_speech_start(self, participant_id: str):
        """Called when AI starts speaking (first audio chunk played)"""
        timestamp = time.time()
        self.ai_speech_start_times[participant_id] = timestamp
        
        # Calculate user-experienced latency
        if participant_id in self.user_speech_end_times:
            user_latency = timestamp - self.user_speech_end_times[participant_id]
            self.user_latencies.append(user_latency)
            
            logger.info(f"[USER LATENCY] Turn {self.conversation_turn_count}: {user_latency:.3f}s")
            logger.debug(f"[USER LATENCY] AI speech started at {timestamp:.3f}")
            
            # Clean up
            del self.user_speech_end_times[participant_id]
            
    def get_user_latency_summary(self):
        """Get comprehensive user latency statistics"""
        if not self.user_latencies:
            return {}
            
        return {
            'total_turns': len(self.user_latencies),
            'avg_user_latency_seconds': statistics.mean(self.user_latencies),
            'median_user_latency_seconds': statistics.median(self.user_latencies),
            'min_user_latency_seconds': min(self.user_latencies),
            'max_user_latency_seconds': max(self.user_latencies),
            'p95_user_latency_seconds': statistics.quantiles(self.user_latencies, n=20)[18] if len(self.user_latencies) >= 2 else statistics.mean(self.user_latencies),
            'estimated_network_overhead_ms': self.estimated_network_overhead_ms,
        }