"""
Users Table will have the following columns:
- id(primary key) --> Created automatically
- Name --> User provided
- Email --> User provided
- Password --> Encrypted Password
- Any other User related data like dark/light mode etc. 
"""

"""
Agents Table will have the following columns:
- id(primary key) --> generated at the time of creating an agent
- agent_name --> generated at the time of creating an agent
- customer_id --> Taken from the user making the agent
- phone_id --> Taken from the phone table
- TTS_Setting --> Json format 
- STT Setting --> Json format
- LLM Setting --> Json format
- bg_noise_setting --> Json format
- backchannelling setting --> Json format
- welcome_msg --> 
"""

"""
Backgound Noise Table:
- id --> Primary Key
- Name --> Name of Noise
- Location --> File location
"""

"""
Service Table:
- id(primary key) --> Added by admin at the time of registering the service
- service_name --> Provided by admin
- service_description --> Provided by admin
- service_pre_requisited --> Provided by admin {phone_num:"", type_of_call:"inbound/outbound"}
"""

"""
Telephone numbers:
- id(primary key) --> Added automatically
- telephone_num --> Provided by user
- provider_id --> Selected by user from dropdown
- agent_id --> Selected by User
- inbound_sip --> Created by User
- outbound_sip --> Created by User
"""

"""
Telephony Table:
- id(Primary key)
- telephony provider
"""

"""
Prompts Table
- id(primary key) --> Created at the time of creating prompt
- version_id --> self-incrementing 
- secondary_id --> Empty if only one version, with second and third version referring to first_version id
- prompt --> Entered by user, json field.
- agent_id --> Added automatically when you write a prompt for the agent
- variables --> Defined at the time of writing the prompt. List of items.
- prompt_commit_msg 
"""

"""
Calls Table:
id
room_num
agent_name
call_started at
ended_at
call_status
metadata
"""


"""
Campaign table will have the following columns:
- id (primary key) --> generated at the time of user creating a campaign.
- customer_id --> Taken from the user who created the campaign.
- campaign_name --> generated at the time of user creating a campaign.
- agent_id --> Taken from the users agents. (Has to be an agent created by the agent)
- redials --> Number of redials attempted (By default 3).
- campaign_status --> Status of the campaign (active, inactive, completed).
- campaign_instruction --> Instructions for the campaign (call later, etc.).
"""

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