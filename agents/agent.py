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
import asyncio
import logging
import os
from dotenv import load_dotenv
from time import perf_counter

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

# Import our refactored modules
from config.voice_config import VoiceSettings, Voice
from metrics import UserLatencyTracker, EnhancedMetricsCollector, measure_network_latency
from handlers.event_handlers import (
    create_conversation_item_handler,
    create_metrics_handler,
    create_speech_handler
)

# 🆕 METRICS INTEGRATION - Add these imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from metrics.simple_recorder import initialize_simple_metrics, get_simple_recorder
    from config.metrics_config import get_metrics_config
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    print("⚠️ Metrics system not available")

print(f"Redis connection established. {r}")

# Load env vars
load_dotenv(dotenv_path=".env.local")
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

async def entrypoint(ctx: JobContext):
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set properly")

    phone_number = ctx.job.metadata if ctx.job.metadata else None
    logger.info(f"Connecting to room {ctx.room.name} to dial {phone_number}")

    # Measure network latency at startup
    measured_latency_ms = await measure_network_latency()

    await ctx.connect()

    # 🆕 METRICS SETUP - Initialize metrics for this call
    call_id = None
    if METRICS_AVAILABLE:
        try:
            config = get_metrics_config()
            if config.enabled:
                try:
                    recorder = get_simple_recorder()
                except RuntimeError:
                    await initialize_simple_metrics(config.agent_name)
                    recorder = get_simple_recorder()
                
                call_id = await recorder.start_call(ctx.room.name, phone_number or "")
                logger.info(f"📊 Metrics tracking started: {call_id}")
                logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
        except Exception as e:
            logger.warning(f"⚠️ Metrics setup failed: {e}")

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
                logger.info("Call answered by user")
                break
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_REJECTED:
                logger.info("User rejected the call")
                # 🆕 End metrics tracking for rejected call
                if METRICS_AVAILABLE and call_id:
                    try:
                        recorder = get_simple_recorder()
                        await recorder.end_call(call_id, "rejected")
                    except:
                        pass
                await ctx.shutdown()
                return
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_UNAVAILABLE:
                logger.info("User unavailable")
                # 🆕 End metrics tracking for unavailable call
                if METRICS_AVAILABLE and call_id:
                    try:
                        recorder = get_simple_recorder()
                        await recorder.end_call(call_id, "unavailable")
                    except:
                        pass
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
            min_silence_duration=0.1,   # Reduce from default 0.5s
            min_speech_duration=0.1,    # Minimum speech to trigger
            max_buffered_speech=5.0,    # Limit buffering
        ),
    )

    # Initialize user latency tracker
    user_latency_tracker = UserLatencyTracker()
    user_latency_tracker.estimated_network_overhead_ms = measured_latency_ms * 2  # Round trip

    # Initialize enhanced metrics collector
    enhanced_metrics = EnhancedMetricsCollector(user_latency_tracker)

    # 🆕 ENHANCED EVENT HANDLERS with metrics integration
    def on_conversation_item_added(event):
        async def handle_conversation_item():
            item = event.item

            if item.role == "user":
                logger.info(f"[ASR] User: {item.text_content}")
                await publish_transcript(ctx.room.name, "user", item.text_content)
                
                # 🆕 Record ASR metric
                if METRICS_AVAILABLE and call_id:
                    try:
                        recorder = get_simple_recorder()
                        await recorder.record_asr_metric(call_id)
                    except:
                        pass
                        
            elif item.role == "assistant":
                logger.info(f"[LLM] Agent: {item.text_content}")
                await publish_transcript(ctx.room.name, "agent", item.text_content)
                
                # 🆕 Record TTS metric
                if METRICS_AVAILABLE and call_id:
                    try:
                        recorder = get_simple_recorder()
                        await recorder.record_tts_metric(call_id)
                    except:
                        pass
        
        asyncio.create_task(handle_conversation_item())
    
    session.on("conversation_item_added")(on_conversation_item_added)
    
    # 🆕 ENHANCED METRICS HANDLER with LLM tracking
    def on_metrics_collected(event: MetricsCollectedEvent):
        # Original metrics code
        from livekit.agents.metrics import log_metrics
        log_metrics(event.metrics)
        enhanced_metrics.collect_metrics_event(event)
        
        # Track user speech end for user latency calculation
        if hasattr(event.metrics, 'end_of_utterance_delay'):
            participant_id = getattr(ctx, 'participant_id', 'default_user')
            user_latency_tracker.on_user_speech_end(participant_id)
        
        # 🆕 Record LLM TTFT
        if METRICS_AVAILABLE and call_id and hasattr(event.metrics, 'ttft'):
            ttft = getattr(event.metrics, 'ttft', 0)
            if ttft > 0:
                try:
                    recorder = get_simple_recorder()
                    asyncio.create_task(recorder.record_llm_metric(call_id, ttft))
                except:
                    pass
    
    session.on("metrics_collected")(on_metrics_collected)
    
    # 🆕 ENHANCED SPEECH HANDLER with user latency tracking
    def on_agent_speech_committed(event):
        # Original speech handling
        participant_id = getattr(ctx, 'participant_id', 'default_user')
        user_latency_tracker.on_ai_speech_start(participant_id)
        
        # 🆕 Record user latency
        if METRICS_AVAILABLE and call_id and hasattr(user_latency_tracker, 'user_latencies') and user_latency_tracker.user_latencies:
            latest_latency = user_latency_tracker.user_latencies[-1]
            try:
                recorder = get_simple_recorder()
                asyncio.create_task(recorder.record_user_latency(call_id, latest_latency))
            except:
                pass
    
    session.on("agent_speech_committed")(on_agent_speech_committed)

    # 🆕 ENHANCED SHUTDOWN CALLBACK with metrics cleanup
    async def enhanced_shutdown():
        try:
            # Original shutdown code
            await enhanced_metrics.log_comprehensive_metrics("call_completed")
            
            # 🆕 End metrics tracking
            if METRICS_AVAILABLE and call_id:
                try:
                    recorder = get_simple_recorder()
                    await recorder.end_call(call_id, "completed")
                    logger.info(f"📊 Metrics tracking ended: {call_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Metrics cleanup failed: {e}")
        
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")
    
    # Add enhanced shutdown callback
    ctx.add_shutdown_callback(enhanced_shutdown)

    # 🆕 PERIODIC PERFORMANCE LOGGING for load testing
    async def log_performance_summary():
        """Log performance summary every 2 minutes during load test"""
        while True:
            try:
                await asyncio.sleep(120)  # Every 2 minutes
                
                if METRICS_AVAILABLE and call_id:
                    try:
                        recorder = get_simple_recorder()
                        stats = await recorder.get_live_stats()
                        
                        logger.info("📈 LOAD TEST STATUS:")
                        logger.info(f"  📞 Active calls: {stats.get('active_calls', 0)}")
                        logger.info(f"  🧠 Total LLM calls: {stats.get('total_llm_calls', 0)}")
                        logger.info(f"  ⏱️  Avg TTFT: {stats.get('avg_ttft_seconds', 0):.3f}s")
                        logger.info(f"  👤 Avg User Latency: {stats.get('avg_user_latency_seconds', 0):.3f}s")
                        logger.info(f"  ⏰ Uptime: {stats.get('uptime_seconds', 0)/60:.1f} minutes")
                    except:
                        pass
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"⚠️ Performance logging error: {e}")

    # Start performance monitoring task for load testing
    if METRICS_AVAILABLE:
        monitoring_task = asyncio.create_task(log_performance_summary())
        
        async def cleanup_monitoring():
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

        ctx.add_shutdown_callback(cleanup_monitoring)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

def prewarm_fnc(proc: JobProcess):
    # load silero weights and store to process userdata
    proc.userdata["vad"] = silero.VAD.load()

if __name__ == "__main__":
    agent_list = ['outbound-caller', 'outbound-caller2', 'outbound-caller3']
    def get_free_agent():
        return agent_list[0]
    agent_ = get_free_agent()
    
    # 🆕 METRICS STATUS LOGGING for load testing
    logger.info("🎯 Starting LiveKit Agent with Load Test Metrics")
    logger.info(f"📊 Agent: {agent_}")
    
    if METRICS_AVAILABLE:
        try:
            config = get_metrics_config()
            logger.info(f"✅ Metrics enabled: {config.agent_name}")
            logger.info(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
            logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
            logger.info(f"🎯 Load test target: {config.target_calls_for_test} calls")
            logger.info(f"📊 Max concurrent: {config.max_concurrent_calls}")
            logger.info("="*60)
            logger.info("🚀 READY FOR LOAD TESTING!")
            logger.info("📋 Monitor progress at: http://localhost:1234")
            logger.info("="*60)
        except Exception as e:
            logger.warning(f"⚠️ Metrics config error: {e}")
    else:
        logger.info("📊 Metrics system not available")
        logger.info("⚠️ Load test monitoring disabled")
    
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_,
            prewarm_fnc=prewarm_fnc,
        )
    )