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
    JobProcess
)
from livekit.plugins import deepgram, openai, silero

from tools.llm_functions import CallAgent
from guardrails.guardrails import GuardrailsLLM
from tts.tts import __get_tts
from prompts import get_prompt
from agent_assist.utils import *

# Agent-Assist-changes
from agent_assist.redis_functions import r

# Import our refactored modules
from config.voice_config import VoiceSettings, Voice
from metrics import UserLatencyTracker, EnhancedMetricsCollector, measure_network_latency
from handlers.event_handlers import (
    create_conversation_item_handler,
    create_metrics_handler,
    create_speech_handler
)

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
                await ctx.shutdown()
                return
            elif participant.disconnect_reason == rtc.DisconnectReason.USER_UNAVAILABLE:
                logger.info("User unavailable")
                await ctx.shutdown()
                return
            await asyncio.sleep(0.1)

    agent = CallAgent(instructions=get_prompt(), ctx=ctx)

    base_llm = openai.LLM()
    guardrails_llm = GuardrailsLLM(llm=base_llm)

    session = AgentSession(
        stt = deepgram.STT(model="nova-3"),
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

    # Set up event handlers
    session.on("conversation_item_added")(
        create_conversation_item_handler(ctx.room.name)
    )
    
    session.on("metrics_collected")(
        create_metrics_handler(enhanced_metrics, user_latency_tracker, ctx)
    )
    
    session.on("agent_speech_committed")(
        create_speech_handler(user_latency_tracker, ctx)
    )

    # Add shutdown callback for comprehensive metrics logging
    ctx.add_shutdown_callback(enhanced_metrics.log_comprehensive_metrics)

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
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_,
            prewarm_fnc=prewarm_fnc,
        )
    )