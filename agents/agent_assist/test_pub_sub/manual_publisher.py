import redis
import json
import time
import random
from msg_simulator import *

def add_to_transcription(new_msg: str, transcript: str) -> str:
    """
    Appends a new message to the existing transcript in a consistent format.

    Args:
        new_msg (str): A message like 'User: text' or 'Human Agent: text'.
        transcript (str): The existing formatted transcript.

    Returns:
        str: The updated transcript with the new message appended.
    """
    # Ensure transcript ends cleanly
    transcript = transcript.strip()

    # Add a newline if the transcript doesn't already end with one
    if not transcript.endswith('\n'):
        transcript += '\n'

    # Append the new message with consistent indentation
    updated_transcript = f'{transcript}                    {new_msg}\n'
    return updated_transcript

def generate_msg_format_for_redis(room_id, speaker, message):
    message_json = {
        "history_id": history_id,
        "timestamp": int(time.time() * 1000),
        "room_id": room_id,
        "speaker": speaker,
        "message": message
    }
    return message_json

# Connect to remote Redis
r = redis.Redis(host='sbi.vaaniresearch.com', port=6379, decode_responses=True)

# history_id = r.incr("global:history_id")

msgs = [
    "Hello, how can I assist you today?",
    "Thank you for reaching out. How may I help you?",
    "I appreciate your message. What can I do for you?",
    "Greetings! How can I be of service?",
    "Hi there! What assistance do you need?",
    "Welcome! What brings you here today?",
    "Good day! How might I support you?",
    "Hello! I'm here to help. What's on your mind?",
    "Thanks for connecting. What can I help you with?",
    "Hi! What would you like assistance with today?",
    "Pleased to meet you. How can I be helpful?",
    "Hello there! What questions do you have for me?",
    "Good to see you! What do you need help with?",
    "Hi! I'm ready to assist. What's your request?",
    "Welcome back! How can I help you this time?",
    "Hello! What task can I help you accomplish?",
    "Greetings! What information are you looking for?",
    "Hi there! How can I make your day easier?",
    "Good morning/afternoon! What can I do for you?",
    "Hello! I'm here and ready to help. What's up?",
    "Thanks for your inquiry. How may I assist?",
    "Hi! What challenge can I help you solve today?",
    "Hello there! What support do you need?",
    "Greetings! How can I be most useful to you?",
    "Hi! What would you like to explore together?"
]

speaker_list = [
    "manual_tester",
    "test_user",
    "test_agent"
]

rooms_list = [
    "room1", "room2", "room3", "room4", "room5"]

room_id = random.choice(['room5']) 
# message_ = random.choice(msgs)
# speaker_ = random.choice(speaker_list)


msgs = 50
i = 1
transcription="""
                    User: "Hello?? Is anyone there?"
                    Human Agent: "Yes sir, I am here. How may I help you."
                """
# while i<msgs:
#     #User response
#     print("*************************")
#     user_msg = asyncio.run(generate_user_query(transcript=transcription))
#     user_response = user_msg['message']
#     message_user = generate_msg_format_for_redis(room_id=room_id, speaker="User", message=user_response)
#     r.publish(room_id, json.dumps(message_user))
#     history_key = f"room_history:{room_id}"
#     r.lpush(history_key, json.dumps(user_response))
#     print(f"{user_response}")
#     print("-----------------------------")

#     updated_transcript = add_to_transcription(user_response, transcription)

#     #Assuming Agent takes time to response
#     # time.sleep(3)

#     #Agent Response
#     agent_msg = asyncio.run(simulate_human_agent(transcript=updated_transcript))
#     agent_response = agent_msg['message']
#     message_agent = generate_msg_format_for_redis(room_id=room_id, speaker="Human Agent", message=agent_response)
#     r.publish(room_id, json.dumps(message_agent))
#     history_key = f"room_history:{room_id}"
#     r.lpush(history_key, json.dumps(agent_response))
#     print(f"Message: {agent_response}")

#     transcription = add_to_transcription(agent_response, updated_transcript)
#     print("####################")
#     i +=1

#     # time.sleep(2)

while i < msgs:
    # print("*************************")

    # --- User Response ---
    history_id = r.incr("global:history_id")
    user_msg = asyncio.run(generate_user_query(transcript=transcription))
    user_response = user_msg['message'].strip()

    message_user = generate_msg_format_for_redis(
        room_id=room_id,
        speaker="User",
        message=user_response
    )
    r.publish(room_id, json.dumps(message_user))

    history_key = f"room_history:{room_id}"
    r.lpush(history_key, json.dumps(user_response))

    # print(user_response)
    # print("-----------------------------")

    # Update transcript with User message
    transcription = add_to_transcription(user_response, transcription)


    time.sleep(2)
    # --- Agent Response ---
    history_id = r.incr("global:history_id")
    agent_msg = asyncio.run(simulate_human_agent(transcript=transcription))
    agent_response = agent_msg['message'].strip()

    message_agent = generate_msg_format_for_redis(
        room_id=room_id,
        speaker="Human Agent",
        message=agent_response
    )
    r.publish(room_id, json.dumps(message_agent))

    r.lpush(history_key, json.dumps(agent_response))

    # print(f"{agent_response}")

    # Update transcript with Agent message
    transcription = add_to_transcription(agent_response, transcription)

    # print("####################")
    time.sleep(3)
    i += 1

    





# # Publish message
# r.publish(room_id, json.dumps(message))

# #Store in Redis
# history_key = f"room_history:{room_id}"
# r.lpush(history_key, json.dumps(message))

# print(f"Message: {message}")

# print(f"Published message to room '{room_id}'")
