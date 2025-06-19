#Used for making calls to the given agent
import subprocess
from dotenv import load_dotenv
import os
import yaml
from call_status import check_call_status
from call_utils import get_room_name_from_result

#Loading the right env variables
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

#Pass the metadata as command line argument as --metadata {"name": "Nitish", "email": "nitish@gmail.com", "phone": "+917055888820"}
def run_agent_call(agent_name, metadata, attempt:int, room_name):
    """"
    This function will take the agent name and metadata as input and run the command to make a call to the agent.
    """
    
    command = ["lk", "dispatch", "create", "--room", room_name, "--agent-name", agent_name,"--metadata", metadata,
        "--api-key", LIVEKIT_API_KEY, "--api-secret", LIVEKIT_API_SECRET,"--url", LIVEKIT_URL]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        curr_room_name = get_room_name_from_result(result)
        print("Command Output:", result.stdout)
        #Parse the room number from here and update the attempt room number.
        #if attempt==0, just enter {0: "curr_room_name"}, else get the attempt value from the campaign_details table for this phone_number
        #then store it in attempts_made dictionary. Further update it like attempts_made['attempt'] = "curr_room_name from result"

    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)



""""
After a successful call dial output, we will update the room_num in the campaign_detail table
Campaign_detail table will have the following columns:
- id (primary key) --> generated at the time of csv upload or ERP sync
- name --> generated at the time of csv upload or ERP sync
- phone --> generated at the time of csv upload or ERP sync
- campaign_id --> Taken from the campaign table
- agent_id --> generated at the time of csv upload or ERP sync
- room_num --> Updated from the result of the run_agent_call function. Is a json field.
- call_status --> Updated from result of the check_call_status function
- Redials --> If call was "Rejected" or "Not picked" Update to 1, go till 3(default), else, 0. This will be used a function which calls run_agent_call function in loop.
- call_later_instruction --> If the user requests a call later, we will parse this instruction before updating the db using a function call from the agent.
"""

