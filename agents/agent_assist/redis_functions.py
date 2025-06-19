import redis.asyncio as redis
import json
import os
import time
from dotenv import load_dotenv

load_dotenv(dotenv_path="/app/.env.local")
redis_host = os.getenv("REDIS_HOST")

r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

async def get_history_id():
    return await r.incr("global:history_id")

async def publish_transcript(room_id, speaker, message):
    history_id = await get_history_id()
    data = {
        "history_id": history_id,
        "timestamp": int(time.time() * 1000),
        "room_id": room_id,
        "speaker": speaker,
        "message": message
    }
    await r.publish(room_id, json.dumps(data))
    history_key = f"room_history:{room_id}"
    await r.lpush(history_key, json.dumps(data))

if __name__ == "__main__":
    # Example usage
    import asyncio
    room_id = "room1"
    speaker = "test_speaker"
    message = "This is a test message"
    
    asyncio.run(publish_transcript(room_id, speaker, message))
    print(f"Published message to room '{room_id}'")