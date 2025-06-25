# import asyncio
# import logging
# import os
# from dotenv import load_dotenv
# from time import perf_counter

# from livekit import rtc, api
# from livekit.agents import (
#     AgentSession,
#     JobContext,
#     WorkerOptions,
#     cli,
#     JobProcess
# )
# from livekit.plugins import deepgram, openai, silero

# from tools.llm_functions import CallAgent
# from guardrails.guardrails import GuardrailsLLM
# from tts.tts import __get_tts
# from prompts import get_prompt
# from agent_assist.utils import *

# # Agent-Assist-changes
# from agent_assist.redis_functions import r

# # Import our refactored modules
# from config.voice_config import VoiceSettings, Voice
# from metrics import UserLatencyTracker, EnhancedMetricsCollector, measure_network_latency
# from handlers.event_handlers import (
#     create_conversation_item_handler,
#     create_metrics_handler,
#     create_speech_handler
# )

# print(f"Redis connection established. {r}")

# # Load env vars
# load_dotenv(dotenv_path=".env.local")
# outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

# logger = logging.getLogger("outbound-caller")
# logger.setLevel(logging.INFO)

# async def entrypoint(ctx: JobContext):
#     if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
#         raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set properly")

#     phone_number = ctx.job.metadata if ctx.job.metadata else None
#     logger.info(f"Connecting to room {ctx.room.name} to dial {phone_number}")

#     # Measure network latency at startup
#     measured_latency_ms = await measure_network_latency()

#     await ctx.connect()

#     if phone_number is not None:
#         participant_name = f"phone_user-{phone_number}"
#         await ctx.api.sip.create_sip_participant(
#             api.CreateSIPParticipantRequest(
#                 room_name=ctx.room.name,
#                 sip_trunk_id=outbound_trunk_id,
#                 sip_call_to=phone_number,
#                 participant_identity=participant_name,
#             )
#         )

#         participant = await ctx.wait_for_participant(identity=participant_name)

#         start_time = perf_counter()
#         while perf_counter() - start_time < 30:
#             call_status = participant.attributes.get("sip.callStatus")
#             if call_status == "active":
#                 logger.info("Call answered by user")
#                 break
#             elif participant.disconnect_reason == rtc.DisconnectReason.USER_REJECTED:
#                 logger.info("User rejected the call")
#                 await ctx.shutdown()
#                 return
#             elif participant.disconnect_reason == rtc.DisconnectReason.USER_UNAVAILABLE:
#                 logger.info("User unavailable")
#                 await ctx.shutdown()
#                 return
#             await asyncio.sleep(0.1)

#     agent = CallAgent(instructions=get_prompt(), ctx=ctx)

#     base_llm = openai.LLM()
#     guardrails_llm = GuardrailsLLM(llm=base_llm)

#     session = AgentSession(
#         stt = deepgram.STT(model="nova-3"),
#         llm=base_llm,
#         tts=deepgram.TTS(),
#         vad=silero.VAD.load(
#             min_silence_duration=0.1,   # Reduce from default 0.5s
#             min_speech_duration=0.1,    # Minimum speech to trigger
#             max_buffered_speech=5.0,    # Limit buffering
#         ),
#     )

#     # Initialize user latency tracker
#     user_latency_tracker = UserLatencyTracker()
#     user_latency_tracker.estimated_network_overhead_ms = measured_latency_ms * 2  # Round trip

#     # Initialize enhanced metrics collector
#     enhanced_metrics = EnhancedMetricsCollector(user_latency_tracker)

#     # Set up event handlers
#     session.on("conversation_item_added")(
#         create_conversation_item_handler(ctx.room.name)
#     )
    
#     session.on("metrics_collected")(
#         create_metrics_handler(enhanced_metrics, user_latency_tracker, ctx)
#     )
    
#     session.on("agent_speech_committed")(
#         create_speech_handler(user_latency_tracker, ctx)
#     )

#     # Add shutdown callback for comprehensive metrics logging
#     ctx.add_shutdown_callback(enhanced_metrics.log_comprehensive_metrics)

#     await session.start(
#         agent=agent,
#         room=ctx.room,
#     )

# def prewarm_fnc(proc: JobProcess):
#     # load silero weights and store to process userdata
#     proc.userdata["vad"] = silero.VAD.load()

# if __name__ == "__main__":
#     agent_list = ['outbound-caller', 'outbound-caller2', 'outbound-caller3']
#     def get_free_agent():
#         return agent_list[0]
#     agent_ = get_free_agent()
#     cli.run_app(
#         WorkerOptions(
#             entrypoint_fnc=entrypoint,
#             agent_name=agent_,
#             prewarm_fnc=prewarm_fnc,
#         )
#     )

# agents/agent.py - YOUR COMPLETE FINAL VERSION WITH METRICS
# agents/agent_enhanced.py - Enhanced agent with full metrics integration

# agents/agent_enhanced_metrics.py - Better metrics integration

import asyncio
import logging
import os
from dotenv import load_dotenv
from time import perf_counter
import redis.asyncio as aioredis
import json
import os
from datetime import datetime

from livekit import rtc, api
from livekit.agents import (
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    JobProcess,
    MetricsCollectedEvent
)
from livekit.plugins import deepgram, openai, silero

from tools.llm_functions import CallAgent
from guardrails.guardrails import GuardrailsLLM
from tts.tts import __get_tts
from prompts import get_prompt
from agent_assist.utils import *

# Agent-Assist-changes
from agent_assist.redis_functions import r, publish_transcript

# Enhanced metrics integration
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from config.enhanced_metrics_config import EnhancedMetricsConfig
    from metrics.enhanced_recorder import EnhancedMetricsRecorder
    ENHANCED_METRICS_AVAILABLE = True
except ImportError:
    ENHANCED_METRICS_AVAILABLE = False
    print("⚠️ Enhanced metrics system not available")

print(f"Redis connection established. {r}")

# Load env vars
load_dotenv(dotenv_path=".env.local")
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
client_name = os.getenv("CLIENT_NAME", "default_client")

logger = logging.getLogger("enhanced-agent-metrics")
logger.setLevel(logging.INFO)

# Global variables for metrics
enhanced_recorder = None
current_call_id = None


async def publish_post_call_event(call_id: str, status: str = "completed", metadata: dict = None):
    """Simple function to publish post-call event to Redis"""
    try:
        # Get Redis config from environment
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB_TRANSCRIPTS", "0"))  # Same as transcripts
        queue_name = os.getenv("POST_CALL_QUEUE_NAME", "post_call_queue")
        
        # Connect to Redis
        redis_client = aioredis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # Publish event
        event_data = {
            "room_id": call_id,
            "action": "call_ended",
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        await redis_client.publish(queue_name, json.dumps(event_data))
        await redis_client.close()
        
        logger.info(f"📤 Published post-call event: {call_id} ({status})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to publish post-call event for {call_id}: {e}")
        return False

async def entrypoint(ctx: JobContext):
    global enhanced_recorder, current_call_id
    
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set properly")

    phone_number = ctx.job.metadata if ctx.job.metadata else None
    logger.info(f"🚀 Enhanced agent connecting to room {ctx.room.name} to dial {phone_number}")

    # 🆕 ENHANCED METRICS SETUP
    if ENHANCED_METRICS_AVAILABLE:
        try:
            config = EnhancedMetricsConfig.from_yaml()
            if config.enabled:
                enhanced_recorder = EnhancedMetricsRecorder(config)
                await enhanced_recorder.initialize()
                
                current_call_id = await enhanced_recorder.start_call(
                    room_name=ctx.room.name,
                    phone_number=phone_number or "",
                    caller_name="Load Test User",
                    client_name=client_name
                )
                logger.info(f"📊 Enhanced metrics tracking started: {current_call_id}")
                logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
        except Exception as e:
            logger.warning(f"⚠️ Enhanced metrics setup failed: {e}")

    await ctx.connect()

    # SIP participant setup (existing code)
    if phone_number is not None:
        participant_name = f"phone_user-{phone_number}"
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_name,
            )
        )

        participant = await ctx.wait_for_participant(identity=participant_name)

        start_time = perf_counter()
        while perf_counter() - start_time < 30:
            call_status = participant.attributes.get("sip.callStatus")
            if call_status == "active":
                logger.info("📞 Call answered by user")
                break
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_REJECTED:
                logger.info("❌ User rejected the call")
                if enhanced_recorder and current_call_id:
                    await enhanced_recorder.end_call(current_call_id, "rejected")
                await ctx.shutdown()
                return
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_UNAVAILABLE:
                logger.info("❌ User unavailable")
                if enhanced_recorder and current_call_id:
                    await enhanced_recorder.end_call(current_call_id, "unavailable")
                await ctx.shutdown()
                return
            await asyncio.sleep(0.1)

    agent = CallAgent(instructions=get_prompt(), ctx=ctx)
    base_llm = openai.LLM()
    guardrails_llm = GuardrailsLLM(llm=base_llm)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=base_llm,
        tts=deepgram.TTS(),
        vad=silero.VAD.load(
            min_silence_duration=0.1,
            min_speech_duration=0.1,
            max_buffered_speech=5.0,
        ),
    )

    # 🆕 ENHANCED EVENT HANDLERS with detailed metrics
    def on_conversation_item_added(event):
        async def handle_conversation_item():
            item = event.item

            if item.role == "user":
                logger.info(f"[ASR] User: {item.text_content}")
                await publish_transcript(ctx.room.name, "user", item.text_content)
                        
            elif item.role == "assistant":
                logger.info(f"[LLM] Agent: {item.text_content}")
                await publish_transcript(ctx.room.name, "agent", item.text_content)
        
        asyncio.create_task(handle_conversation_item())
    
    session.on("conversation_item_added")(on_conversation_item_added)
    
    # 🆕 ENHANCED METRICS HANDLER - This captures the logged metrics
    def on_metrics_collected(event: MetricsCollectedEvent):
        from livekit.agents.metrics import log_metrics
        log_metrics(event.metrics)
        
        # Store enhanced metrics
        if enhanced_recorder and current_call_id:
            asyncio.create_task(
                store_metrics_from_event(event.metrics, current_call_id)
            )
    
    session.on("metrics_collected")(on_metrics_collected)

    # 🆕 ENHANCED SHUTDOWN CALLBACK
    # async def enhanced_shutdown():
    #     try:
    #         logger.info("🏁 Enhanced agent shutdown initiated")
            
    #         if enhanced_recorder and current_call_id:
    #             await enhanced_recorder.end_call(current_call_id, "completed")
    #             logger.info(f"📊 Enhanced metrics tracking ended: {current_call_id}")
    #             await enhanced_recorder.cleanup()
        
    #     except Exception as e:
    #         logger.error(f"❌ Enhanced shutdown error: {e}")
    
    async def enhanced_shutdown():
        try:
            logger.info("🏁 Enhanced agent shutdown initiated")
            
            if enhanced_recorder and current_call_id:
                await enhanced_recorder.end_call(current_call_id, "completed")
                logger.info(f"📊 Enhanced metrics tracking ended: {current_call_id}")
                
                # 🆕 ADD THIS: Publish post-call event
                try:
                    await publish_post_call_event(
                        call_id=current_call_id,
                        status="completed",
                        metadata={
                            "agent_name": "enhanced-agent-1",
                            "end_reason": "normal_completion",
                            "client_id": os.getenv("CLIENT_ID", "default")
                        }
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to publish post-call event: {e}")
                
                await enhanced_recorder.cleanup()
            
        except Exception as e:
            logger.error(f"❌ Enhanced shutdown error: {e}")

    ctx.add_shutdown_callback(enhanced_shutdown)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

async def store_metrics_from_event(metrics, call_id):
    """Store metrics from MetricsCollectedEvent into enhanced recorder"""
    if not enhanced_recorder or not call_id:
        return
    
    try:
        # Extract different types of metrics
        for metric in metrics:
            metric_type = getattr(metric, 'type', None) or type(metric).__name__
            
            if 'llm' in metric_type.lower() or hasattr(metric, 'ttft'):
                # LLM metrics
                ttft = getattr(metric, 'ttft', 0)
                input_tokens = getattr(metric, 'prompt_tokens', 0) or getattr(metric, 'input_tokens', 0)
                output_tokens = getattr(metric, 'completion_tokens', 0) or getattr(metric, 'output_tokens', 0)
                
                if ttft > 0:  # Valid TTFT
                    await enhanced_recorder.record_detailed_llm_metric(
                        call_id, ttft, input_tokens, output_tokens
                    )
                    logger.debug(f"📊 Stored LLM metric: TTFT={ttft:.3f}s, tokens={input_tokens}/{output_tokens}")
            
            elif 'tts' in metric_type.lower() or hasattr(metric, 'ttfb'):
                # TTS metrics
                ttfb = getattr(metric, 'ttfb', 0)
                audio_duration = getattr(metric, 'audio_duration', 0)
                
                if ttfb > 0 or audio_duration > 0:
                    await enhanced_recorder.record_detailed_tts_metric(
                        call_id, ttfb, audio_duration, 0
                    )
                    logger.debug(f"📊 Stored TTS metric: TTFB={ttfb:.3f}s, duration={audio_duration:.3f}s")
            
            elif 'stt' in metric_type.lower() or 'asr' in metric_type.lower() or hasattr(metric, 'audio_duration'):
                # STT/ASR metrics
                audio_duration = getattr(metric, 'audio_duration', 0)
                
                if audio_duration > 0:
                    await enhanced_recorder.record_detailed_asr_metric(
                        call_id, audio_duration, 0
                    )
                    logger.debug(f"📊 Stored ASR metric: duration={audio_duration:.3f}s")
            
            elif 'eou' in metric_type.lower() or hasattr(metric, 'end_of_utterance_delay'):
                # EOU metrics
                eou_delay = getattr(metric, 'end_of_utterance_delay', 0)
                
                if 0 < eou_delay < 30:  # Reasonable range
                    await enhanced_recorder.record_detailed_eou_metric(call_id, eou_delay)
                    logger.debug(f"📊 Stored EOU metric: delay={eou_delay:.3f}s")
            
    except Exception as e:
        logger.error(f"❌ Error storing metrics: {e}")

def prewarm_fnc(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

if __name__ == "__main__":
    agent_list = ['enhanced-agent-metrics-1', 'enhanced-agent-metrics-2', 'enhanced-agent-metrics-3']
    def get_free_agent():
        return agent_list[0]
    agent_ = get_free_agent()
    
    logger.info("🎯 Starting Enhanced LiveKit Agent with Call-by-Call Metrics")
    logger.info(f"📊 Agent: {agent_}")
    
    if ENHANCED_METRICS_AVAILABLE:
        try:
            config = EnhancedMetricsConfig.from_yaml()
            logger.info(f"✅ Enhanced metrics enabled: {config.client_name}")
            logger.info(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
            logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
            logger.info("="*60)
            logger.info("🚀 READY FOR CALL-BY-CALL METRICS TRACKING!")
            logger.info("📋 View individual call metrics at dashboard")
            logger.info("="*60)
        except Exception as e:
            logger.warning(f"⚠️ Enhanced metrics config error: {e}")
    else:
        logger.info("📊 Enhanced metrics system not available")
    
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_,
            prewarm_fnc=prewarm_fnc,
        )
    )