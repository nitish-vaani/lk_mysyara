import statistics
import logging
from livekit.agents import metrics
from .user_latency import UserLatencyTracker

logger = logging.getLogger("outbound-caller")

class EnhancedMetricsCollector:
    """Enhanced metrics collector with component and user-level tracking"""
    
    def __init__(self, user_latency_tracker: UserLatencyTracker):
        # LLM Metrics
        self.llm_calls = 0
        self.llm_ttft_times = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        # ASR Metrics  
        self.asr_calls = 0
        self.total_asr_audio_duration = 0.0
        
        # TTS Metrics
        self.tts_calls = 0
        self.tts_ttfb_times = []
        self.total_tts_audio_duration = 0.0
        
        # EOU Metrics
        self.eou_delays = []
        
        # E2E Component Metrics
        self.e2e_component_latencies = []
        
        # User latency tracker reference
        self.user_latency_tracker = user_latency_tracker
        
        # Usage collector for overall summary
        self.usage_collector = metrics.UsageCollector()
    
    def collect_metrics_event(self, event):
        """Main method to collect all metrics from event"""
        # Collect usage summary
        self.usage_collector.collect(event.metrics)
        
        # Check if it's an LLM metrics event
        if hasattr(event.metrics, 'ttft') or 'ttft' in str(event.metrics):
            self._collect_llm_from_event(event.metrics)
        
        # Check if it's a TTS metrics event  
        if hasattr(event.metrics, 'ttfb') or 'ttfb' in str(event.metrics):
            self._collect_tts_from_event(event.metrics)
            
        # Check if it's an STT metrics event
        if hasattr(event.metrics, 'audio_duration') or 'audio_duration' in str(event.metrics):
            self._collect_stt_from_event(event.metrics)
            
        # Check if it's an EOU metrics event
        if hasattr(event.metrics, 'end_of_utterance_delay') or 'end_of_utterance_delay' in str(event.metrics):
            self._collect_eou_from_event(event.metrics)
    
    def _collect_llm_from_event(self, metrics):
        """Extract LLM metrics from event"""
        try:
            self.llm_calls += 1
            
            # Get TTFT
            ttft = getattr(metrics, 'ttft', None)
            if ttft is not None:
                self.llm_ttft_times.append(ttft)
            
            # Get token counts - try different attribute names
            prompt_tokens = (getattr(metrics, 'prompt_tokens', None) or 
                           getattr(metrics, 'input_tokens', None) or 0)
            completion_tokens = (getattr(metrics, 'completion_tokens', None) or 
                               getattr(metrics, 'output_tokens', None) or 0)
            
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            
            logger.debug(f"[METRICS] LLM collected - TTFT: {ttft}, Prompt: {prompt_tokens}, Completion: {completion_tokens}")
            
        except Exception as e:
            logger.warning(f"Error collecting LLM metrics: {e}")
    
    def _collect_tts_from_event(self, metrics):
        """Extract TTS metrics from event"""
        try:
            self.tts_calls += 1
            
            # Get TTFB
            ttfb = getattr(metrics, 'ttfb', None)
            if ttfb is not None:
                self.tts_ttfb_times.append(ttfb)
            
            # Get audio duration
            audio_duration = getattr(metrics, 'audio_duration', None)
            if audio_duration is not None:
                self.total_tts_audio_duration += audio_duration
                
            logger.debug(f"[METRICS] TTS collected - TTFB: {ttfb}, Duration: {audio_duration}")
            
        except Exception as e:
            logger.warning(f"Error collecting TTS metrics: {e}")
    
    def _collect_stt_from_event(self, metrics):
        """Extract STT metrics from event"""
        try:
            # Only count if it's actually an STT event (not TTS with audio_duration)
            if not hasattr(metrics, 'ttfb'):  # TTS events also have audio_duration
                self.asr_calls += 1
                
                audio_duration = getattr(metrics, 'audio_duration', None)
                if audio_duration is not None:
                    self.total_asr_audio_duration += audio_duration
                    
                logger.debug(f"[METRICS] STT collected - Duration: {audio_duration}")
                
        except Exception as e:
            logger.warning(f"Error collecting STT metrics: {e}")
    
    def _collect_eou_from_event(self, metrics):
        """Extract EOU metrics from event"""
        try:
            eou_delay = getattr(metrics, 'end_of_utterance_delay', None)
            if eou_delay is not None:
                # Filter out timestamp values (very large numbers)
                if eou_delay > 1000000:  # Likely a timestamp
                    logger.debug(f"[METRICS] EOU delay appears to be timestamp: {eou_delay}, skipping")
                    return
                
                # Only accept reasonable EOU delays (between 0 and 30 seconds)
                if 0 <= eou_delay <= 30:
                    self.eou_delays.append(eou_delay)
                    
                    # Calculate E2E component latency if we have recent LLM and TTS data
                    if self.llm_ttft_times and self.tts_ttfb_times:
                        # Use the most recent TTFT and TTFB
                        recent_ttft = self.llm_ttft_times[-1]
                        recent_ttfb = self.tts_ttfb_times[-1]
                        e2e_component_latency = eou_delay + recent_ttft + recent_ttfb
                        self.e2e_component_latencies.append(e2e_component_latency)
                        
                    logger.debug(f"[METRICS] EOU collected - Delay: {eou_delay}")
                else:
                    logger.debug(f"[METRICS] EOU delay out of reasonable range: {eou_delay}s, skipping")
                
        except Exception as e:
            logger.warning(f"Error collecting EOU metrics: {e}")

    def get_comprehensive_summary(self):
        """Get all metrics with component and user-level analysis"""
        
        # Get usage summary for character count
        usage_summary = self.usage_collector.get_summary()
        
        # Component-level statistics
        avg_ttft = statistics.mean(self.llm_ttft_times) if self.llm_ttft_times else 0
        avg_ttfb = statistics.mean(self.tts_ttfb_times) if self.tts_ttfb_times else 0
        avg_eou = statistics.mean(self.eou_delays) if self.eou_delays else 0
        avg_e2e_component = statistics.mean(self.e2e_component_latencies) if self.e2e_component_latencies else 0
        
        # Component-level medians
        median_ttft = statistics.median(self.llm_ttft_times) if self.llm_ttft_times else 0
        median_ttfb = statistics.median(self.tts_ttfb_times) if self.tts_ttfb_times else 0
        median_eou = statistics.median(self.eou_delays) if self.eou_delays else 0
        median_e2e_component = statistics.median(self.e2e_component_latencies) if self.e2e_component_latencies else 0
        
        # Component-level percentiles
        p95_ttft = statistics.quantiles(self.llm_ttft_times, n=20)[18] if len(self.llm_ttft_times) >= 2 else avg_ttft
        p95_eou = statistics.quantiles(self.eou_delays, n=20)[18] if len(self.eou_delays) >= 2 else avg_eou
        p95_e2e_component = statistics.quantiles(self.e2e_component_latencies, n=20)[18] if len(self.e2e_component_latencies) >= 2 else avg_e2e_component
        
        # User-level statistics
        user_latency_summary = self.user_latency_tracker.get_user_latency_summary()
        
        return {
            # LLM Metrics
            'llm_calls': self.llm_calls,
            'avg_ttft_seconds': avg_ttft,
            'median_ttft_seconds': median_ttft,
            'p95_ttft_seconds': p95_ttft,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_prompt_tokens + self.total_completion_tokens,
            
            # ASR Metrics
            'asr_calls': self.asr_calls,
            'total_asr_audio_duration_seconds': self.total_asr_audio_duration,
            'total_asr_audio_duration_minutes': self.total_asr_audio_duration / 60,
            
            # TTS Metrics
            'tts_calls': self.tts_calls,
            'avg_ttfb_seconds': avg_ttfb,
            'median_ttfb_seconds': median_ttfb,
            'total_tts_audio_duration_seconds': self.total_tts_audio_duration,
            'total_tts_characters': getattr(usage_summary, 'tts_characters_count', 0),
            
            # Component E2E Metrics
            'total_eou_events': len(self.eou_delays),
            'avg_eou_delay_seconds': avg_eou,
            'median_eou_delay_seconds': median_eou,
            'p95_eou_delay_seconds': p95_eou,
            'total_e2e_component_turns': len(self.e2e_component_latencies),
            'avg_e2e_component_latency_seconds': avg_e2e_component,
            'median_e2e_component_latency_seconds': median_e2e_component,
            'p95_e2e_component_latency_seconds': p95_e2e_component,
            
            # User-Level Metrics
            'user_latency_summary': user_latency_summary,
            
            # Raw usage summary
            'usage_summary': usage_summary
        }

    async def log_comprehensive_metrics(self, reason=None):
        """Log comprehensive metrics summary with component and user-level analysis"""
        summary = self.get_comprehensive_summary()
        usage_summary = summary['usage_summary']
        user_summary = summary['user_latency_summary']
        
        logger.info("="*70)
        logger.info("[COMPREHENSIVE METRICS SUMMARY]")
        logger.info("="*70)
        
        # Usage Summary (from livekit)
        logger.info(f"[USAGE SUMMARY] {usage_summary}")
        
        # Enhanced LLM Metrics
        logger.info(f"[LLM METRICS]")
        logger.info(f"  Total LLM Calls: {summary['llm_calls']}")
        logger.info(f"  Average TTFT: {summary['avg_ttft_seconds']:.3f}s")
        logger.info(f"  Median TTFT: {summary['median_ttft_seconds']:.3f}s ⭐")
        logger.info(f"  95th Percentile TTFT: {summary['p95_ttft_seconds']:.3f}s")
        logger.info(f"  Total Token Usage: {summary['total_tokens']}")
        
        # Enhanced ASR Metrics
        logger.info(f"[ASR METRICS]")
        logger.info(f"  Total ASR Calls: {summary['asr_calls']}")
        logger.info(f"  Total Audio Duration: {summary['total_asr_audio_duration_seconds']:.2f}s ({summary['total_asr_audio_duration_minutes']:.2f}m)")
        
        # Enhanced TTS Metrics  
        logger.info(f"[TTS METRICS]")
        logger.info(f"  Total TTS Calls: {summary['tts_calls']}")
        logger.info(f"  Median TTFB: {summary['median_ttfb_seconds']:.3f}s ⭐")
        logger.info(f"  Total Characters Synthesized: {summary['total_tts_characters']}")
        
        # Component E2E Metrics
        logger.info(f"[COMPONENT E2E LATENCY]")
        logger.info(f"  Total Component Turns: {summary['total_e2e_component_turns']}")
        logger.info(f"  Median EOU Delay: {summary['median_eou_delay_seconds']:.3f}s ⭐")
        logger.info(f"  Median Component E2E: {summary['median_e2e_component_latency_seconds']:.3f}s ⭐")
        logger.info(f"  95th Percentile Component E2E: {summary['p95_e2e_component_latency_seconds']:.3f}s")
        
        # User-Level Metrics
        if user_summary:
            logger.info(f"[USER-EXPERIENCED LATENCY] 🌍")
            logger.info(f"  Total User Turns: {user_summary['total_turns']}")
            logger.info(f"  Average User Latency: {user_summary['avg_user_latency_seconds']:.3f}s")
            logger.info(f"  Median User Latency: {user_summary['median_user_latency_seconds']:.3f}s 🎯")
            logger.info(f"  95th Percentile User Latency: {user_summary['p95_user_latency_seconds']:.3f}s")
            logger.info(f"  Min/Max User Latency: {user_summary['min_user_latency_seconds']:.3f}s / {user_summary['max_user_latency_seconds']:.3f}s")
            logger.info(f"  Estimated Network Overhead: {user_summary['estimated_network_overhead_ms']:.0f}ms")
        else:
            logger.info(f"[USER-EXPERIENCED LATENCY] No user turns recorded")
        
        # Performance Analysis
        logger.info(f"[PERFORMANCE ANALYSIS]")
        
        # Component analysis
        if summary['median_eou_delay_seconds'] > 1.0:
            logger.info(f"  ⚠️  Component EOU Delay High: {summary['median_eou_delay_seconds']:.3f}s")
        else:
            logger.info(f"  ✅ Component EOU Delay Good: {summary['median_eou_delay_seconds']:.3f}s")
            
        component_total = summary['median_eou_delay_seconds'] + summary['median_ttft_seconds'] + summary['median_ttfb_seconds']
        logger.info(f"  📊 Median Component E2E: {component_total:.3f}s")
        
        # User experience analysis
        if user_summary:
            user_median = user_summary['median_user_latency_seconds']
            if user_median < 1.5:
                rating = "🟢 Excellent"
            elif user_median < 2.0:
                rating = "🟡 Good"
            elif user_median < 3.0:
                rating = "🟠 Acceptable"
            else:
                rating = "🔴 Poor"
                
            logger.info(f"  🎯 User Experience: {rating} ({user_median:.3f}s median)")
            
            # Calculate estimated network impact
            if 'estimated_network_overhead_ms' in user_summary:
                network_ms = user_summary['estimated_network_overhead_ms']
                component_ms = component_total * 1000
                logger.info(f"  🌐 Network Impact: {network_ms:.0f}ms ({network_ms/(network_ms+component_ms)*100:.1f}% of total)")
        
        logger.info("="*70)