#Use this to add a free agent to the call.
import subprocess
from dotenv import load_dotenv
import os
import yaml

from identify_free_agent import free_human_agent, free_transcriber_agent, free_main_agent
from call_utils import get_room_name_from_result



load_dotenv(dotenv_path=".env.local")
with open("config/engine_config.yml", "r") as file:
    config = yaml.safe_load(file)
if config["cloud"]:
    LIVEKIT_URL = os.getenv("LIVEKIT_URL_CLOUD")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY_CLOUD")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET_CLOUD")
else:
    LIVEKIT_URL = os.getenv("LIVEKIT_URL_LOCAL")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY_LOCAL")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET_LOCAL")

def add_human_agent_to_room(room_name, main_outbound_agent, use_case=None):
    """
    We will look for a free agent, and then add that agent to the room.
    Positive result: {status: True, msg: "Call getting transferred to agent"}
    Negative result: {status: False, msg: "No free agent"}
    Negative result msgs: ["No free agent", "Agent didn't pick", "Agent busy", "Number not reachable", "Telephony issue on agent side"]
    """
    result = {}
    free_agent = free_human_agent(use_case)

    if not free_agent.status:
        result['status'] = False
        result['msg'] = "No free agent"
        return result

    else:
        human_agent_name = free_agent['payload']['name']
        human_agent_number = free_agent['payload']['phone']
        metadata = {
            "name": f"human_agent_{human_agent_name}",
            "phone": human_agent_number
        }

    command = ["lk", "dispatch", "create", "--room", room_name, "--agent-name", main_outbound_agent,"--metadata", metadata,
    "--api-key", LIVEKIT_API_KEY, "--api-secret", LIVEKIT_API_SECRET,"--url", LIVEKIT_URL]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        curr_room_name = get_room_name_from_result(result)
        #This is just the dispatch request, not the actual confirmation that the human has been added
        #We want the confirmation for the human agent to be added.
        #Once the human agent is added, I want the main agent to brief the human agent about the call and also
        #send a msg to the frontend pub-sub
        if curr_room_name['status'] and curr_room_name['payload']['room_num'] == room_name:
            pass


    except:
        pass




