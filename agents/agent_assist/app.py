from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import aioredis
import asyncio
import json
import os
from dotenv import load_dotenv
from redis_functions import publish_transcript, r
from utils import *
from worker_management import *



load_dotenv(dotenv_path="/app/.env.local")
redis_host = os.getenv("REDIS_HOST")

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(BASE_DIR, "test_pub_sub/html")

# Mount the static directory properly
app.mount("/html", StaticFiles(directory=HTML_DIR), name="html")

# Serve the HTML page directly at root "/"
@app.get("/")
async def get_html():
    return FileResponse(os.path.join(HTML_DIR, "test_pub_sub.html"))

@app.get("/ws-test")
async def get_html():
    return FileResponse(os.path.join(HTML_DIR, "ws_test.html"))


# @app.websocket("/ws/{room_id}")
# async def websocket_endpoint(websocket: WebSocket, room_id: str):
#     await websocket.accept()
#     start_worker(room_id)
#     redis = aioredis.from_url(f"redis://{redis_host}:6379")
#     pubsub = redis.pubsub()
#     await pubsub.subscribe(room_id)

#     try:
#         while True:
#             message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
#             if message:
#                 data = json.loads(message['data'])
#                 await websocket.send_json(data)
#             await asyncio.sleep(0.1)
#     except WebSocketDisconnect:
#         await pubsub.unsubscribe(room_id)
#         await pubsub.close()


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    
    # Start the worker for this room
    start_worker(room_id)
    
    redis = aioredis.from_url(f"redis://{redis_host}:6379")
    pubsub = redis.pubsub()
    await pubsub.subscribe(room_id)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message['data'])
                await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for room {room_id}")
    # finally:
    #     # Cleanup
    #     print("Going here for cleanup")
    #     await pubsub.unsubscribe(room_id)
    #     await pubsub.close()
    #     await redis.close()
    #     disconnect_worker(room_id)
    #     print("Cleaned up!")


@app.post("/publish/{room_id}")
async def publish_llm_msg(room_id: str, content: dict):
    """
    Get the chat context from the user and publish it to Redis channel.
    """
    message = process_content(content)

    if message['status_code'] == 200:
        # print(f"Publishing message to room '{room_id}': {message['message']}")
        await publish_transcript(room_id, "llm", message['message'])
        return {"status": "success", "message": "Content processed and published."}
    else:
        # print(f"Failed to process content: {message['message']}")
        return {"status": "error", "message": "Failed to process content."}



## This code should go in the main backend.py
# @app.get("/api/{conversation_id}")
# async def get_conversation_status(conversation_id: str) -> dict:
#     """
#     We will take the conversation_id and get the room_id. If conversation has ended,
#     we will return the transcript, else we will return the room_id.
#     """
#     if conversation_id == "ended123":
#         return {
#             "status": "ended",
#             "transcript": "Hello, this is the stored transcript for ended123."
#         }
#     else:
#         return {
#             "status": "live",
#             "room_id": f"room{conversation_id}"
#         }

