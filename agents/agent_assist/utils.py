import json
import random

def process_content(content: dict) -> dict:

    """
    We will take the chat context dictionary, and process it to return a dictionary.
    we will do llm processing here and return the llm response.
    """
    
    message = random.choice([
        "Hello, how can I assist you today?",
        "Thank you for reaching out. How may I help you?",
        "I appreciate your message. What can I do for you?",
        "Greetings! How can I be of service?",
        "Hi there! What assistance do you need?",
    ])
    result = {
        "status_code": 200,
        "message": message,
    }

    # print(f"Content received and processed: {content}")
    return result