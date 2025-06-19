# # import asyncio
# # import logging
# # from livekit.agents.metrics import log_metrics
# # from livekit.agents import MetricsCollectedEvent

# # # Agent-Assist-changes
# # from agent_assist.redis_functions import publish_transcript

# # logger = logging.getLogger("outbound-caller")

# # async def handle_conversation_item(event, room_name: str):
# #     """Handle conversation item events for transcript publishing"""
# #     item = event.item

# #     if item.role == "user":
# #         logger.info(f"[ASR] User: {item.text_content}")
# #         await publish_transcript(room_name, "user", item.text_content)
# #     elif item.role == "assistant":
# #         logger.info(f"[LLM] Agent: {item.text_content}")
# #         await publish_transcript(room_name, "agent", item.text_content)

# # def create_conversation_item_handler(room_name: str):
# #     """Create a conversation item handler for a specific room"""
# #     def on_conversation_item_added(event):
# #         asyncio.create_task(handle_conversation_item(event, room_name))
# #     return on_conversation_item_added

# # def create_metrics_handler(enhanced_metrics, user_latency_tracker, ctx):
# #     """Create a metrics collection handler"""
# #     def on_metrics_collected(event: MetricsCollectedEvent):
# #         # Log the original metrics
# #         log_metrics(event.metrics)
        
# #         # Collect with our enhanced collector
# #         enhanced_metrics.collect_metrics_event(event)
        
# #         # Track user speech end for user latency calculation
# #         if hasattr(event.metrics, 'end_of_utterance_delay'):
# #             # Get participant ID from context - try multiple ways to get it
# #             participant_id = None
            
# #             # Try to get from room participants
# #             if hasattr(ctx, 'room') and ctx.room and len(ctx.room.remote_participants) > 0:
# #                 # Get the first remote participant (should be the phone user)
# #                 participant_id = list(ctx.room.remote_participants.keys())[0]
            
# #             # Fallback to default
# #             if not participant_id:
# #                 participant_id = 'default_user'
                
# #             logger.debug(f"[USER LATENCY] Tracking EOU for participant: {participant_id}")
# #             user_latency_tracker.on_user_speech_end(participant_id)
    
# #     return on_metrics_collected

# # def create_speech_handler(user_latency_tracker, ctx):
# #     """Create an agent speech handler"""
# #     def on_agent_speech_start(event):
# #         """Called when agent starts speaking"""
# #         # Get participant ID - try multiple ways
# #         participant_id = None
        
# #         # Try to get from room participants
# #         if hasattr(ctx, 'room') and ctx.room and len(ctx.room.remote_participants) > 0:
# #             # Get the first remote participant (should be the phone user)
# #             participant_id = list(ctx.room.remote_participants.keys())[0]
        
# #         # Fallback to default
# #         if not participant_id:
# #             participant_id = 'default_user'
            
# #         logger.debug(f"[USER LATENCY] Tracking speech start for participant: {participant_id}")
# #         user_latency_tracker.on_ai_speech_start(participant_id)
    
# #     return on_agent_speech_start

# import asyncio
# import logging
# from livekit.agents.metrics import log_metrics
# from livekit.agents import MetricsCollectedEvent

# # Agent-Assist-changes
# from agent_assist.redis_functions import publish_transcript

# logger = logging.getLogger("outbound-caller")

# async def handle_conversation_item(event, room_name: str, user_latency_tracker=None):
#     """Handle conversation item events for transcript publishing"""
#     item = event.item

#     if item.role == "user":
#         logger.info(f"[ASR] User: {item.text_content}")
#         await publish_transcript(room_name, "user", item.text_content)
        
#         # Track user speech end here - when we get the final transcript
#         if user_latency_tracker:
#             # Use a simple participant ID since this is when speech actually ended
#             user_latency_tracker.on_user_speech_end("phone_user")
            
#     elif item.role == "assistant":
#         logger.info(f"[LLM] Agent: {item.text_content}")
#         await publish_transcript(room_name, "agent", item.text_content)

# def create_conversation_item_handler(room_name: str, user_latency_tracker=None):
#     """Create a conversation item handler for a specific room"""
#     def on_conversation_item_added(event):
#         asyncio.create_task(handle_conversation_item(event, room_name, user_latency_tracker))
#     return on_conversation_item_added

# def create_metrics_handler(enhanced_metrics, user_latency_tracker, ctx):
#     """Create a metrics collection handler"""
#     def on_metrics_collected(event: MetricsCollectedEvent):
#         # Log the original metrics
#         log_metrics(event.metrics)
        
#         # Collect with our enhanced collector
#         enhanced_metrics.collect_metrics_event(event)
        
#         # Don't track user speech end here anymore - we do it in conversation_item_added
        
#     return on_metrics_collected

# def create_speech_handler(user_latency_tracker, ctx):
#     """Create an agent speech handler"""
#     def on_agent_speech_start(event):
#         """Called when agent starts speaking"""
#         logger.debug(f"[USER LATENCY] Agent speech committed, tracking start for phone_user")
#         user_latency_tracker.on_ai_speech_start("phone_user")
    
#     return on_agent_speech_start

import asyncio
import logging
from livekit.agents.metrics import log_metrics
from livekit.agents import MetricsCollectedEvent

# Agent-Assist-changes
from agent_assist.redis_functions import publish_transcript

logger = logging.getLogger("outbound-caller")

async def handle_conversation_item(event, room_name: str):
    """Handle conversation item events for transcript publishing"""
    item = event.item

    if item.role == "user":
        logger.info(f"[ASR] User: {item.text_content}")
        await publish_transcript(room_name, "user", item.text_content)
    elif item.role == "assistant":
        logger.info(f"[LLM] Agent: {item.text_content}")
        await publish_transcript(room_name, "agent", item.text_content)

def create_conversation_item_handler(room_name: str):
    """Create a conversation item handler for a specific room"""
    def on_conversation_item_added(event):
        asyncio.create_task(handle_conversation_item(event, room_name))
    return on_conversation_item_added

def create_metrics_handler(enhanced_metrics, user_latency_tracker, ctx):
    """Create a metrics collection handler"""
    def on_metrics_collected(event: MetricsCollectedEvent):
        # Log the original metrics
        log_metrics(event.metrics)
        
        # Collect with our enhanced collector
        enhanced_metrics.collect_metrics_event(event)
        
        # Track user speech end for user latency calculation
        if hasattr(event.metrics, 'end_of_utterance_delay'):
            # Get participant ID from context (you may need to adjust this)
            participant_id = getattr(ctx, 'participant_id', 'default_user')
            user_latency_tracker.on_user_speech_end(participant_id)
    
    return on_metrics_collected

def create_speech_handler(user_latency_tracker, ctx):
    """Create an agent speech handler"""
    def on_agent_speech_start(event):
        """Called when agent starts speaking"""
        participant_id = getattr(ctx, 'participant_id', 'default_user')
        user_latency_tracker.on_ai_speech_start(participant_id)
    
    return on_agent_speech_start