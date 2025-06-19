from prompt_examples.graytitude import prompt as graytitude_prompt
from prompt_examples.air_india import prompt as air_india_prompt
from prompt_examples.test import prompt as test_prompt
from prompt_examples.test_welcome_msg import welcome_msg
from utils import current_time
# time_now = current_time(timezone="America/Los_Angeles")

prompt_ = f"{air_india_prompt}"
def get_prompt(timezone: str = "Asia/Kolkata") -> str:
    time_now = current_time(timezone=timezone)
    prompt = prompt_.replace("{time_now}", time_now)
    return prompt

def get_welcome_message() -> str:
    return welcome_msg

if __name__ == "__main__":
    value = get_prompt()
    print(value)