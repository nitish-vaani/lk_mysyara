import json
import random
import asyncio

from openai import OpenAI
from dotenv import load_dotenv
import json
from datetime import datetime
from test_prompts.human_agent_prompt import transcript as human_agent_prompt
from test_prompts.user_prompt import transcript as user_prompt
import os

load_dotenv("/app/llm_calls_module/.env")
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Instantiate the client
client = OpenAI(api_key=api_key)

# async def generate_user_query(transcript) -> dict:

#     """
#     We will take the chat context dictionary, and process it to return a dictionary.
#     we will do llm processing here and return the llm response. 
#     """

#     # print(f"Content received for response generation: {content}")
#     user = f"""
#     {user_prompt}
#     transcript: {transcript}
#     """

#     human_agent = f"""
#     {human_agent_prompt}
#     transcript: {transcript}
#     """

#     try:
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo-0125",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": human_agent
#                 },
#                 {
#                     "role": "user",
#                     "content": user
#                 }
#             ],
#             temperature=0.3
#         )
#         content = response.choices[0].message.content
#         if content.startswith("```json"):
#             content = content[7:]
#         if content.endswith("```"):
#             content = content[:-3]

#         content = content.strip()
#         # print(f"Processed content: {content}")
#         response = {
#             "status_code": 200,
#             "message": content
#         }
#         return response
    
#     except Exception as e:
#         return {
#             "status_code": 500,
#             "message": f"An error occurred while processing the content: {str(e)}"
#         }

# async def simulate_human_agent(transcript) -> dict:

#     """
#     We will take the chat context dictionary, and process it to return a dictionary.
#     we will do llm processing here and return the llm response.
#     """

#     # print(f"Content received for response generation: {content}")
#     user = f"""
#     {user_prompt}
#     transcript: {transcript}
#     """

#     human_agent = f"""
#     {human_agent_prompt}
#     transcript: {transcript}
#     """

#     try:
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo-0125",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": user
#                 },
#                 {
#                     "role": "user",
#                     "content": human_agent
#                 }
#             ],
#             temperature=0.3
#         )
#         content = response.choices[0].message.content
#         if content.startswith("```json"):
#             content = content[7:]
#         if content.endswith("```"):
#             content = content[:-3]

#         content = content.strip()
#         # print(f"Processed content: {content}")
#         response = {
#             "status_code": 200,
#             "message": content
#         }
#         return response
    
#     except Exception as e:
#         return {
#             "status_code": 500,
#             "message": f"An error occurred while processing the content: {str(e)}"
#         }

async def generate_user_query(transcript) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": user_prompt
                    # "content": "You are a user in a customer support conversation. Respond naturally, briefly, and consistently. Do not speak as the human agent. Your tone can reflect some mild frustration if relevant."
                },
                {
                    "role": "user",
                    "content": f"The following is the ongoing conversation transcript:\n\n{transcript}\n\nWhat would you like to say next?"
                }
            ],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        return {
            "status_code": 200,
            "message": content
        }

    except Exception as e:
        return {
            "status_code": 500,
            "message": f"An error occurred while processing the content: {str(e)}"
        }

async def simulate_human_agent(transcript) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": user_prompt
                    # "content": "You are a professional customer support agent. Be empathetic and helpful. Do not impersonate the user."
                },
                {
                    "role": "user",
                    "content": f"The following is the ongoing conversation transcript:\n\n{transcript}\n\nWhat would the human agent say next?"
                }
            ],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        return {
            "status_code": 200,
            "message": content
        }

    except Exception as e:
        return {
            "status_code": 500,
            "message": f"An error occurred while processing the content: {str(e)}"
        }



if __name__ == "__main__":
    transcription="""
                    User: "Hello?? Is anyone there?"
                    Human Agent: "Yes sir, I am here. How may I help you."
                """
    # response_user = asyncio.run(generate_user_query(transcript=transcription))
    response_agent = asyncio.run(simulate_human_agent(transcript=transcription))
    # print(f"user: {response_user}")
    print(f"user: {response_agent}")
