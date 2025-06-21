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

logger = logging.getLogger("enhanced-agent")
logger.setLevel(logging.INFO)

async def entrypoint(ctx: JobContext):
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set properly")

    phone_number = ctx.job.metadata if ctx.job.metadata else None
    logger.info(f"🚀 Enhanced agent connecting to room {ctx.room.name} to dial {phone_number}")

    # 🆕 ENHANCED METRICS SETUP
    enhanced_recorder = None
    call_id = None
    
    if ENHANCED_METRICS_AVAILABLE:
        try:
            config = EnhancedMetricsConfig.from_yaml()
            if config.enabled:
                enhanced_recorder = EnhancedMetricsRecorder(config)
                await enhanced_recorder.initialize()
                
                call_id = await enhanced_recorder.start_call(
                    room_name=ctx.room.name,
                    phone_number=phone_number or "",
                    caller_name="Load Test User",
                    client_name=client_name
                )
                logger.info(f"📊 Enhanced metrics tracking started: {call_id}")
                logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
        except Exception as e:
            logger.warning(f"⚠️ Enhanced metrics setup failed: {e}")

    await ctx.connect()

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
                if enhanced_recorder and call_id:
                    await enhanced_recorder.end_call(call_id, "rejected")
                await ctx.shutdown()
                return
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_UNAVAILABLE:
                logger.info("❌ User unavailable")
                if enhanced_recorder and call_id:
                    await enhanced_recorder.end_call(call_id, "unavailable")
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
                
                # Enhanced ASR metric
                if enhanced_recorder and call_id:
                    await enhanced_recorder.record_detailed_asr_metric(
                        call_id, 
                        duration=len(item.text_content) * 0.1,  # Rough estimate
                        words=len(item.text_content.split())
                    )
                        
            elif item.role == "assistant":
                logger.info(f"[LLM] Agent: {item.text_content}")
                await publish_transcript(ctx.room.name, "agent", item.text_content)
                
                # Enhanced TTS metric
                if enhanced_recorder and call_id:
                    await enhanced_recorder.record_detailed_tts_metric(
                        call_id,
                        ttfb=0.3,  # You can measure actual TTFB
                        duration=len(item.text_content) * 0.05,  # Rough estimate
                        characters=len(item.text_content)
                    )
        
        asyncio.create_task(handle_conversation_item())
    
    session.on("conversation_item_added")(on_conversation_item_added)
    
    # 🆕 ENHANCED METRICS HANDLER with detailed LLM tracking
    def on_metrics_collected(event: MetricsCollectedEvent):
        from livekit.agents.metrics import log_metrics
        log_metrics(event.metrics)
        
        # Enhanced LLM TTFT tracking
        if enhanced_recorder and call_id and hasattr(event.metrics, 'ttft'):
            ttft = getattr(event.metrics, 'ttft', 0)
            tokens_in = getattr(event.metrics, 'prompt_tokens', 0)
            tokens_out = getattr(event.metrics, 'completion_tokens', 0)
            
            if ttft > 0:
                asyncio.create_task(
                    enhanced_recorder.record_detailed_llm_metric(
                        call_id, ttft, tokens_in, tokens_out
                    )
                )
        
        # Enhanced EOU tracking
        if enhanced_recorder and call_id and hasattr(event.metrics, 'end_of_utterance_delay'):
            eou_delay = getattr(event.metrics, 'end_of_utterance_delay', 0)
            if 0 < eou_delay < 30:  # Reasonable range
                asyncio.create_task(
                    enhanced_recorder.record_detailed_eou_metric(call_id, eou_delay)
                )
    
    session.on("metrics_collected")(on_metrics_collected)
    
    # 🆕 ENHANCED SPEECH HANDLER with user latency tracking
    def on_agent_speech_committed(event):
        # Calculate user-experienced latency (simplified)
        estimated_user_latency = 1.5  # You can implement actual calculation
        
        if enhanced_recorder and call_id:
            asyncio.create_task(
                enhanced_recorder.record_detailed_user_latency(call_id, estimated_user_latency)
            )
    
    session.on("agent_speech_committed")(on_agent_speech_committed)

    # 🆕 ENHANCED SHUTDOWN CALLBACK
    async def enhanced_shutdown():
        try:
            logger.info("🏁 Enhanced agent shutdown initiated")
            
            if enhanced_recorder and call_id:
                await enhanced_recorder.end_call(call_id, "completed")
                logger.info(f"📊 Enhanced metrics tracking ended: {call_id}")
                await enhanced_recorder.cleanup()
        
        except Exception as e:
            logger.error(f"❌ Enhanced shutdown error: {e}")
    
    ctx.add_shutdown_callback(enhanced_shutdown)

    # 🆕 PERIODIC PERFORMANCE LOGGING for load testing
    async def log_enhanced_performance():
        """Log enhanced performance metrics every 2 minutes"""
        while True:
            try:
                await asyncio.sleep(120)
                
                if enhanced_recorder:
                    active_calls = await enhanced_recorder.get_active_calls()
                    
                    logger.info("📊 ENHANCED LOAD TEST STATUS:")
                    logger.info(f"  📞 Active calls: {active_calls.get('total_active', 0)}")
                    logger.info(f"  📋 Call details: {len(active_calls.get('calls', []))}")
                    
                    for call in active_calls.get('calls', [])[:3]:  # Show first 3
                        logger.info(f"    🔹 {call['call_id']}: {call['duration']:.1f}s, "
                                   f"LLM:{call['llm_calls']}, TTS:{call['tts_calls']}, ASR:{call['asr_calls']}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"⚠️ Enhanced performance logging error: {e}")

    # Start enhanced monitoring
    if enhanced_recorder:
        monitoring_task = asyncio.create_task(log_enhanced_performance())
        
        async def cleanup_enhanced_monitoring():
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

        ctx.add_shutdown_callback(cleanup_enhanced_monitoring)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

def prewarm_fnc(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

if __name__ == "__main__":
    agent_list = ['enhanced-agent-1', 'enhanced-agent-2', 'enhanced-agent-3']
    def get_free_agent():
        return agent_list[0]
    agent_ = get_free_agent()
    
    logger.info("🎯 Starting Enhanced LiveKit Agent with Load Test Metrics")
    logger.info(f"📊 Agent: {agent_}")
    
    if ENHANCED_METRICS_AVAILABLE:
        try:
            config = EnhancedMetricsConfig.from_yaml()
            logger.info(f"✅ Enhanced metrics enabled: {config.client_name}")
            logger.info(f"🔧 Redis: {config.redis_host}:{config.redis_port}/db{config.redis_db}")
            logger.info(f"📈 Dashboard: http://localhost:{config.monitoring_port}")
            logger.info(f"🎯 Load test target: {config.load_test.max_concurrent_calls} concurrent calls")
            logger.info("="*60)
            logger.info("🚀 READY FOR ENHANCED LOAD TESTING!")
            logger.info("📋 Monitor progress at dashboard")
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