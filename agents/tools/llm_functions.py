# import asyncio
# import json
# import logging
# from typing import Annotated
# from livekit import api, rtc
# from livekit.agents import llm
# import aiohttp
# from dotenv import load_dotenv
# import os
# import subprocess
# from livekit.api import RoomParticipantIdentity, UpdateParticipantRequest, ParticipantPermission

# load_dotenv(dotenv_path=".env.local")
# event_id = os.getenv("EVENT_TYPE_ID")
# url_ = os.getenv("base_url")
# lk_api_key = os.getenv("LIVEKIT_API_KEY")
# lk_url = os.getenv("LIVEKIT_URL")
# lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
# lk_sip_outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")


# logger = logging.getLogger("outbound-caller")


# class CallActions(llm.FunctionContext):
#     """
#     Detect user intent and perform actions
#     """

#     def __init__(
#         self, *, api: api.LiveKitAPI, participant: rtc.RemoteParticipant, room: rtc.Room
#     ):
#         super().__init__()
#         self.api = api
#         self.participant = participant
#         self.room = room

#     async def hangup(self):
#         try:
#             await self.api.room.remove_participant(
#                 api.RoomParticipantIdentity(
#                     room=self.room.name,
#                     identity=self.participant.identity,
#                 )
#             )
#         except Exception as e:
#             # it's possible that the user has already hung up, this error can be ignored
#             logger.info(f"received error while ending call: {e}")

#     @llm.ai_callable()
#     async def end_call(self):
#         """Called when the user wants to end the call"""
#         logger.info(f"ending the call for {self.participant.identity}")
#         await self.hangup()

#     @llm.ai_callable()
#     async def detected_answering_machine(self):
#         """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
#         logger.info(f"detected answering machine for {self.participant.identity}")
#         await self.hangup()

#     @llm.ai_callable()
#     async def customer_exists(
#         self,
#         customer_id: Annotated[str, "The customer ID"]
#     ):
#         """
#         Checks if a customer exists in the database.
#         """
#         logger.info(f"Checking existence of customer ID: {customer_id}")

#         #url = "https://sbi.vaaniresearch.com/api/customer_exists/"  # Update with actual API URL
#         url = url_ + "/customer_exists/"
        
#         logger.info(f"Making post request to {url}")

#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json={"customer_id": customer_id}) as response:
#                     print(f"Making post request to {url}")
#                     logger.info(f"Response from API: {response.status}")
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)
#                     else:
#                         logger.error(f"Error from API: {response.status}")
#                         return json.dumps({"error": "Failed to fetch customer details."})
#             except Exception as e:
#                 logger.error(f"Exception in customer_exists: {e}")
#                 return json.dumps({"error": "Internal error occurred."})

#     @llm.ai_callable()
#     async def get_calender_details(
#         self,
#         start_time: Annotated[str, "The start time of the appointment"],
#         end_time: Annotated[str, "The end time of the appointment"],
#         ):
#         """
#         Fetches available calendar times for a given event ID.
#         """
#         logger.info(f"Fetching calendar details for event ID: {event_id}")

#         #url = f"http://sbi.vaaniresearch.com:8002/api/get_calender_details/{event_id}"  # Update with actual API URL
#         url = url_ + "/get_calender_details/" + event_id

#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json={"start_time": start_time, "end_time": end_time}) as response:
#                     logger.info(f"Response from API: {response.status}")
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)
#                     else:
#                         logger.error(f"Error from API: {response.status}")
#                         return json.dumps({"error": "Failed to fetch calendar details."})
#             except Exception as e:
#                 logger.error(f"Exception in get_calender_details: {repr(e)}")
#                 return json.dumps({"error": f"Internal error: {repr(e)}"})


# #Have to make changes in the below functions
#     @llm.ai_callable()
#     async def confirm_appointment(
#         self,
#         slot: Annotated[str, "The slot chosen by the user"],
#         # event_id: Annotated[str, "The event ID"],
#         name: Annotated[str, "The name of the participant"],
#         email: Annotated[str, "The email of the participant"],
#     ):
#         """
#         Called when the user confirms their appointment. Use this tool only when they are certain about the date and time.
#         """
#         logger.info(f"Confirming appointment for {self.participant.identity} at {slot}")

#         #url = "https://sbi.vaaniresearch.com/api/confirm_appointment/"
#         url = url_ + "/confirm_appointment/"

#         payload = {"event_id": event_id,
#                     "slot": slot,
#                     "name": name,
#                     "email": email}

#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json=payload) as response:
#                     logger.info(f"API response status: {response.status}")
                    
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)  # Return actual API response
#                     else:
#                         logger.error(f"API Error: {response.status}")
#                         return json.dumps({"error": "Failed to confirm appointment."})
#             except Exception as e:
#                 logger.error(f"Exception in confirm_appointment: {repr(e)}")
#                 return json.dumps({"error": f"Internal error: {repr(e)}"})



#     @llm.ai_callable()
#     async def update_customer_booking(
#         self,
#         slot: Annotated[str, "The slot chosen by the user"],
#         name: Annotated[str, "The name of the participant"],
#         email: Annotated[str, "The email of the participant"],
#         ):
#         """
#         Update customer booking details.
#         """
#         logger.info(f"Updating customer booking details for {self.participant.identity}")

#         payload = {"event_id": event_id,
#                     "slot": slot,
#                     "name": name,
#                     "email": email}

#         #url = "https://sbi.vaaniresearch.com/api/update_customer_booking/"
#         url = url_ + "/update_customer_booking/"
#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json=payload) as response:
#                     logger.info(f"API response status: {response.status}")
                    
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)  # Return actual API response
#                     else:
#                         logger.error(f"API Error: {response.status}")
#                         return json.dumps({"error": "Failed to confirm appointment."})
#             except Exception as e:
#                 logger.error(f"Exception in confirm_appointment: {repr(e)}")
#                 return json.dumps({"error": f"Internal error: {repr(e)}"})

#     @llm.ai_callable()
#     async def get_customer_booking(
#         self,
#         slot: Annotated[str, "The slot chosen by the user"],
#         name: Annotated[str, "The name of the participant"],
#         email: Annotated[str, "The email of the participant"],
#         ):
#         """
#         Fetch customer booking details.
#         """
#         logger.info(f"Fetching customer booking details for {self.participant.identity}")
#         payload = {"event_id": event_id,
#                     "slot": slot,
#                     "name": name,
#                     "email": email}
#         #url = "https://sbi.vaaniresearch.com/api/get_customer_booking/"
#         url = url_ + "/get_customer_booking/"
#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json=payload) as response:
#                     logger.info(f"API response status: {response.status}")
                    
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)  # Return actual API response
#                     else:
#                         logger.error(f"API Error: {response.status}")
#                         return json.dumps({"error": "Failed to confirm appointment."})
#             except Exception as e:
#                 logger.error(f"Exception in confirm_appointment: {repr(e)}")
#                 return json.dumps({"error": f"Internal error: {repr(e)}"})
    
#     @llm.ai_callable()
#     async def cancel_customer_booking(
#         self,
#         slot: Annotated[str, "The slot chosen by the user"],
#         name: Annotated[str, "The name of the participant"],
#         email: Annotated[str, "The email of the participant"],
#         ):
#         """
#         Fetch customer booking details and then cancel the booking.
#         """
#         logger.info(f"Fetching and cancelling customer details for {self.participant.identity}")
#         payload = {"event_id": event_id,
#                     "slot": slot,
#                     "name": name,
#                     "email": email}
#         #url = "https://sbi.vaaniresearch.com/api/cancel_customer_booking/"
#         url = url_ + "/cancel_customer_booking/"
#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(url, json=payload) as response:
#                     logger.info(f"API response status: {response.status}")
                    
#                     if response.status == 200:
#                         data = await response.json()
#                         return json.dumps(data)  # Return actual API response
#                     else:
#                         logger.error(f"API Error: {response.status}")
#                         return json.dumps({"error": "Failed to confirm appointment."})
#             except Exception as e:
#                 logger.error(f"Exception in confirm_appointment: {repr(e)}")
#                 return json.dumps({"error": f"Internal error: {repr(e)}"})

#     @llm.ai_callable()
#     async def get_room_details(self):
#         """Returns details about the current room."""
        
#         return {
#             "room_name": self.room.name,
#             "participant_id": self.participant.sid,
#             "participant_identity": self.participant.identity,
#             #"room_created_at": self.room.creation_time.isoformat() if self.room.creation_time else "Unknown",
#         }
    
#     @llm.ai_callable()
#     async def transfer_to_observer_agent(self):
#         """
#         Joins an existing LiveKit room and connects a call using the observer agent.

#         """
#         logger.info(f"Transferring call to observer agent for {self.participant.identity}")
#         room_name = self.room.name
#         CMD = [
#                 "lk", "room", "participants", "list", room_name,
#                 "--api-key", lk_api_key,
#                 "--api-secret", lk_api_secret,
#                 "--url", lk_url,
#             ]

#         cmd_result = subprocess.run(CMD, check=True, capture_output=True, text=True)
#         participants = cmd_result.stdout.splitlines()
#         agent_participant = [p for p in participants if p.strip().startswith("agent-")]
#         correct_identity = agent_participant[0].split()[0] if agent_participant else None
#         logger.info(f"Participants in room {self.room.name}: {participants}")
#         command = [
#             "lk", "dispatch", "create",
#             "--room", self.room.name,
#             "--agent-name", "observer-agent",
#             "--api-key", lk_api_key,
#             "--api-secret", lk_api_secret,
#             "--url", lk_url
#         ]

#         try:
#             result = subprocess.run(command, check=True, capture_output=True, text=True)
#             async with api.LiveKitAPI(
#                     url=lk_url,
#                     api_key=lk_api_key,
#                     api_secret=lk_api_secret
#                 ) as lkapi:
#                     # 2. Remove the current participant from the room
#                     logger.info(f"Removing participant {correct_identity} from room {room_name}")
#                     await lkapi.room.update_participant(UpdateParticipantRequest(
#                         room=room_name,
#                         identity=correct_identity,
#                         permission=ParticipantPermission(
#                             can_subscribe=False,
#                             can_publish=False,
#                             can_publish_data=False,
#                         ),
#                         ))
#             logger.info("Main agent's metadata updated to set 'muted' flag.")
#             return f"Call started successfully: {result.stdout}"
#         except subprocess.CalledProcessError as e:
#             return f"Error starting call: {e.stderr}"

#     @llm.ai_callable()
#     async def transfer_to_human_agent(
#         self, 
#         agent_phone: Annotated[str, "The phone number of the human agent to call"]
#     ):
#         """
#         Transfers the call to a human agent by calling their phone number and connecting them to the same room.
#         Use this when the customer needs to speak to a human agent.
#         """
#         logger.info(f"Transferring to human agent at {agent_phone} in room {self.room.name}")
#         room_name = self.room.name
#         CMD = [
#                 "lk", "room", "participants", "list", room_name,
#                 "--api-key", lk_api_key,
#                 "--api-secret", lk_api_secret,
#                 "--url", lk_url,
#             ]

#         cmd_result = subprocess.run(CMD, check=True, capture_output=True, text=True)
#         participants = cmd_result.stdout.splitlines()
#         agent_participant = [p for p in participants if p.strip().startswith("agent-")]
#         correct_identity = agent_participant[0].split()[0] if agent_participant else None
#         logger.info(f"Participants in room {self.room.name}: {participants}")
        
#         try:
#             # Create a SIP participant for the human agent
#             async with api.LiveKitAPI(
#                 url=lk_url,
#                 api_key=lk_api_key,
#                 api_secret=lk_api_secret,
#             ) as lkapi:
#                 # Add the human agent to the room via SIP
#                 await lkapi.sip.create_sip_participant(
#                     api.CreateSIPParticipantRequest(
#                         room_name=self.room.name,
#                         sip_trunk_id=lk_sip_outbound_trunk_id,  # Use your SIP trunk ID
#                         sip_call_to=agent_phone,  # The phone number to dial
#                         participant_identity="human-agent",  # Fixed identity for the human agent
#                     )
#                 )
#                 logger.info(f"Created SIP participant for human agent with phone {agent_phone}")
                
#                 # Wait for human agent to connect
#                 await asyncio.sleep(3)
                
#                 # Inform the customer about the transfer
#                 transfer_message = "I'm transferring you to a human agent who can better assist you. Please hold while I connect you."
                
#                 # After transfer message is delivered, set AI agent to inactive 
#                 # (you can also remove the AI agent if preferred)
#                 async def after_transfer():
#                     await asyncio.sleep(5)  # Wait for message to be delivered
                    
#                     # Either mute the AI agent or remove it altogether
#                     # Option 1: Mark AI agent as inactive but keep it in the room
#                     await lkapi.room.update_participant(
#                         api.UpdateParticipantRequest(
#                             room=self.room.name,
#                             identity=self.room.local_participant.identity,
#                             metadata=json.dumps({"status": "inactive"}),
#                         )
#                     )
#                     logger.info("AI agent marked as inactive")


#     #Use this below option to remove the AI agent completely
#                 #     async with api.LiveKitAPI(
#                 #         url=lk_url,
#                 #         api_key=lk_api_key,
#                 #         api_secret=lk_api_secret
#                 #     ) as lkapi:
#                 #         # 2. Remove the current participant from the room
#                 #         logger.info(f"Removing participant {correct_identity} from room {room_name}")
#                 #         await lkapi.room.update_participant(UpdateParticipantRequest(
#                 #             room=room_name,
#                 #             identity=correct_identity,
#                 #             permission=ParticipantPermission(
#                 #                 can_subscribe=False,
#                 #                 can_publish=False,
#                 #                 can_publish_data=False,
#                 #             ),
#                 #             ))
#                 # logger.info("Main agent's metadata updated to set 'muted' flag.")
                    
#                     # Option 2: Remove AI agent completely (uncomment if preferred)
#                     # await lkapi.room.remove_participant(
#                     #     api.RoomParticipantIdentity(
#                     #         room=self.room.name,
#                     #         identity=self.room.local_participant.identity,
#                     #     )
#                     # )
#                     # logger.info("AI agent removed from room")
                
#                 # Start the after-transfer process
#                 asyncio.create_task(after_transfer())
                
#                 return transfer_message
                
#         except Exception as e:
#             logger.error(f"Error transferring to human agent: {e}")
#             return "I apologize, but I'm unable to transfer you to a human agent at this time. Let's continue our conversation."
            

import asyncio
import json
import logging
from typing import Annotated
from livekit import api, rtc
from livekit.agents import Agent, function_tool, RunContext, JobContext
import aiohttp
import os
from dotenv import load_dotenv
import subprocess
from agent_assist.identify_free_agent import *

load_dotenv(dotenv_path=".env.local")
event_id = os.getenv("EVENT_TYPE_ID")
base_url = os.getenv("base_url")

load_dotenv(dotenv_path=".env.local")
event_id = os.getenv("EVENT_TYPE_ID")
url_ = os.getenv("base_url")
lk_api_key = os.getenv("LIVEKIT_API_KEY")
lk_url = os.getenv("LIVEKIT_URL")
lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
lk_sip_outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

logger = logging.getLogger("outbound-caller")

class CallAgent(Agent):

    # def __init__(self, ctx: JobContext):
    #     super().__init__()
    #     self.ctx = ctx
    #     self.register_tools()

    def __init__(self, instructions: str, ctx: JobContext):
        super().__init__(instructions=instructions)
        self.ctx = ctx
        # self.register_tools()


    @function_tool()
    async def end_call(self, context: RunContext):
        """Called when the user wants to end the call"""
        logger.info(f"Ending the call for {context.participant.identity}")
        await context.room.disconnect()

    @function_tool()
    async def detected_answering_machine(self, context: RunContext):
        """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
        logger.info(f"Detected answering machine for {context.participant.identity}")
        await context.room.disconnect()

    @function_tool()
    async def customer_exists(
        self,
        context: RunContext,
        customer_id: Annotated[str, "The customer ID"]
    ):
        """Checks if a customer exists in the database."""
        logger.info(f"Checking existence of customer ID: {customer_id}")
        url = f"{base_url}/customer_exists/"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json={"customer_id": customer_id}) as response:
                    logger.info(f"Response from API: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.error(f"Error from API: {response.status}")
                        return {"error": "Failed to fetch customer details."}
            except Exception as e:
                logger.error(f"Exception in customer_exists: {e}")
                return {"error": "Internal error occurred."}
            
    

    @function_tool()
    async def transfer_to_human_agent(
        self, 
        # agent_phone: Annotated[str, "The phone number of the human agent to call"]
    ):
        """
        Transfers the call to a human agent by calling their phone number and connecting them to the same room.
        Use this when the customer needs to speak to a human agent.
        """
        logger.info(f"Transferring to human agent in room {self.room.name}")
        room_name = self.room.name
        CMD = [
                "lk", "room", "participants", "list", room_name,
                "--api-key", lk_api_key,
                "--api-secret", lk_api_secret,
                "--url", lk_url,
            ]

        cmd_result = subprocess.run(CMD, check=True, capture_output=True, text=True)
        participants = cmd_result.stdout.splitlines()
        agent_participant = [p for p in participants if p.strip().startswith("agent-")]
        correct_identity = agent_participant[0].split()[0] if agent_participant else None
        logger.info(f"Participants in room {self.room.name}: {participants}")

        #Get the free agent.
        agent_phone = free_human_agent()


        
        try:
            # Create a SIP participant for the human agent
            async with api.LiveKitAPI(
                url=lk_url,
                api_key=lk_api_key,
                api_secret=lk_api_secret,
            ) as lkapi:
                # Add the human agent to the room via SIP
                await lkapi.sip.create_sip_participant(
                    api.CreateSIPParticipantRequest(
                        room_name=self.room.name,
                        sip_trunk_id=lk_sip_outbound_trunk_id,  # Use your SIP trunk ID
                        sip_call_to=agent_phone,  # The phone number to dial
                        participant_identity="human-agent",  # Fixed identity for the human agent
                    )
                )
                logger.info(f"Created SIP participant for human agent with phone {agent_phone}")
                
                # Wait for human agent to connect
                await asyncio.sleep(3)
                
                # Inform the customer about the transfer
                transfer_message = "I'm transferring you to a human agent who can better assist you. Please hold while I connect you."
                
                # After transfer message is delivered, set AI agent to inactive 
                # (you can also remove the AI agent if preferred)
                async def after_transfer():
                    await asyncio.sleep(5)  # Wait for message to be delivered
                    
                    # Either mute the AI agent or remove it altogether
                    # Option 1: Mark AI agent as inactive but keep it in the room
                    await lkapi.room.update_participant(
                        api.UpdateParticipantRequest(
                            room=self.room.name,
                            identity=self.room.local_participant.identity,
                            metadata=json.dumps({"status": "inactive"}),
                        )
                    )
                    logger.info("AI agent marked as inactive")


    #Use this below option to remove the AI agent completely
                #     async with api.LiveKitAPI(
                #         url=lk_url,
                #         api_key=lk_api_key,
                #         api_secret=lk_api_secret
                #     ) as lkapi:
                #         # 2. Remove the current participant from the room
                #         logger.info(f"Removing participant {correct_identity} from room {room_name}")
                #         await lkapi.room.update_participant(UpdateParticipantRequest(
                #             room=room_name,
                #             identity=correct_identity,
                #             permission=ParticipantPermission(
                #                 can_subscribe=False,
                #                 can_publish=False,
                #                 can_publish_data=False,
                #             ),
                #             ))
                # logger.info("Main agent's metadata updated to set 'muted' flag.")
                    
                    # Option 2: Remove AI agent completely (uncomment if preferred)
                    # await lkapi.room.remove_participant(
                    #     api.RoomParticipantIdentity(
                    #         room=self.room.name,
                    #         identity=self.room.local_participant.identity,
                    #     )
                    # )
                    # logger.info("AI agent removed from room")
                
                # Start the after-transfer process
                asyncio.create_task(after_transfer())
                
                return transfer_message
                
        except Exception as e:
            logger.error(f"Error transferring to human agent: {e}")
            return "I apologize, but I'm unable to transfer you to a human agent at this time. Let's continue our conversation."


    # @function_tool()
    # async def get_room_details(self):
    #     """Returns details about the current room."""

        
    #     return {
    #         "room_name": self.ctx.room.name,
    #         # "participant_id": self.participant.sid,
    #         # "participant_identity": self.participant.identity,
    #         #"room_created_at": self.room.creation_time.isoformat() if self.room.creation_time else "Unknown",
    #     }


    # @function_tool()
    # async def get_room_details(self):
    #     """Returns details about the current room."""
        
    #     return {
    #         "room_name": self.room.name,
    #         "participant_id": self.participant.sid,
    #         "participant_identity": self.participant.identity,
    #         #"room_created_at": self.room.creation_time.isoformat() if self.room.creation_time else "Unknown",
    #     }

    @function_tool()
    async def get_room_details(self, context: RunContext):
        """Returns details about the current room."""
        room = self.ctx.room

        return room.name

        # return {
        #     "room_name": context.room.name,
        #     "participant_id": context.participant.sid,
        #     "participant_identity": context.participant.identity,
        #     # "room_created_at": context.room.creation_time.isoformat() if context.room.creation_time else "Unknown",
        # }