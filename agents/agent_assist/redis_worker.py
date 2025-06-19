"""
Subscribes to the pub-sub channel and keeps waiting for msgs.
If msg from a particular speaker is received, it will send a post api request to /publish/{room_id}
with the transcript dictionary.
The whole chat can be accessed by using the api: http://sbi.vaaniresearch.com:8002/api/room_history/{room_id}
"""

#Imports
import asyncio
import redis
import json
import requests
import aiohttp
import time
import aioredis
from redis_functions import *


filter_list = []
disconnection_timeout = 60  # seconds

async def publish_transcription(room_id: str, transcription: str):
    # url = f"http://sbi.vaaniresearch.com:1248/publish/{room_id}"
    url = f"http://sbi.vaaniresearch.com:1247/agent_assist/response_generation"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
            "transcription": transcription
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            status = response.status
            resp_text = await response.text()
            print(f"Response [{status}]: {resp_text}")
            try:
                resp_json = json.loads(resp_text)
                message = resp_json.get("message", "")
            except json.JSONDecodeError:
                message = resp_text
            # print(f"Response: {response['message']}")
            await publish_transcript(room_id, "llm", message)
            return status, resp_text

async def get_chat_history(room_id: str):
    """
    Get the chat history from Redis for the given room_id.
    """

    redis = aioredis.from_url(f"redis://sbi.vaaniresearch.com:6379", decode_responses=True)
    history_key = f"room_history:{room_id}"
    messages = await redis.lrange(history_key, 0, -1)
    try:
        parsed = [json.loads(msg) for msg in messages]
        final_msg = ""
        for msg in parsed[::-1]:  # Reverse the order to get the latest messages first
            if msg['speaker'] in filter_list:
                continue
            final_msg += f"{msg['speaker']}: {msg['message']}\n"

    except Exception:
        parsed = []

    # print(f"get_chat_history function called")
    return final_msg

async def subscribe_to_channel(room_id: str):
    """
    Subscribe to the Redis channel and listen for messages.
    If no message is received for 60 seconds, disconnect.
    """
    r = redis.Redis(host='sbi.vaaniresearch.com', port=6379, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(room_id)

    history_subscribed = await get_chat_history(room_id)

    inactivity_timeout = disconnection_timeout 
    last_message_time = time.time()

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message:
                last_message_time = time.time()  # Reset the timer

                data = json.loads(message['data'])
                history_subscribed += f"{data['speaker']}: {data['message']}\n"

                if data.get('speaker') in ["User"]:
                    print("################################################")
                    start_time = time.perf_counter()
                    print(f"history: {history_subscribed}")
                    content = {
                        "transcript": history_subscribed
                    }
                    await publish_transcription(room_id, content)
                    time_taken = time.perf_counter() - start_time
                    print(f"Time taken to process and publish transcription: {time_taken:.2f} seconds")
                    print("################################################")

            # Check for inactivity timeout
            if time.time() - last_message_time > inactivity_timeout:
                print(f"No messages received for {inactivity_timeout} seconds. Disconnecting.")
                break

            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await pubsub.unsubscribe(room_id)
        await pubsub.aclose()


if __name__ == "__main__":
    #Take the room_id from the user
    import sys
    room_id = sys.argv[1]
    asyncio.run(subscribe_to_channel(room_id))
    # room_id = "room1"
    # print(f"Starting subscription to channel: {room_id}")
    # asyncio.run(subscribe_to_channel(room_id))
    # # asyncio.run(get_chat_history(room_id))