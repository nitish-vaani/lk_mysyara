from datetime import datetime
import pytz

def current_time(timezone: str = "GMT") -> str:
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("GMT")

    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

# # Example Usage
# print(current_time("Asia/Kolkata"))
# print(current_time("America/New_York"))
# print(current_time("Invalid/Timezone"))  
