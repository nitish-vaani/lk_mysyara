
#We will have all kind of small utils functions here

def get_room_name_from_result(result):
    """
    Parse the result to get the room id. Returns room id
    Positive output: {status: True, payload: {room_num: "room_number"}, msg: "Success"}
    Negative output: {status: False, payload: {}, msg: "Failed due to reason"}
    """
    pass

def remove_participant_from_room(room_name, participant):
    """
    Verify that the agent exists in that room and then remove them from the room
    """
    pass

def add_participant_to_room(room_name, participant):
    """
    Verify that the room exists and then add the participant to the room.
    """
    pass

def update_free_agent(agent_id, agent_type):
    """
    Take the agent_id and then update if the agent is free to take calls etc.
    agent_type is human, main, transcriber etc.
    """
    pass