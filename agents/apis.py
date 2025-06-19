from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import requests
import os
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv(dotenv_path=".env.local")
BASE_URL = os.getenv("base_url")
cal_api_key = os.getenv("cal_api_key")
cal_base_url = os.getenv("CALCOM_URL")


#Pydantic model classes 
# class UserCreate(BaseModel):
#     user_id: str
#     username: str
#     contact_number: str
#     password: str

# class UserLogin(BaseModel):
#     username: str
#     password: str

# # class Conversation Create(BaseModel):
# #     agent_id: str
# #     user_id: str

# class PhoneNumberRequest(BaseModel):
#     phone_number: str

# class ConversationCreate(BaseModel):
#     user_id: str
#     agent_id: str
#     name: str
#     contact_number: str

# class FeedbackCreate(BaseModel):
#     conversation_id: str
#     user_id: str
#     feedback_text: str
#     felt_natural: Optional[int] = None
#     response_speed: Optional[int] = None
#     interruptions: Optional[int] = None

# class ModelCreate(BaseModel):
#     model_id: str
#     model_name: str
#     client: str

# class ModelUpdate(BaseModel):
#     model_name: str | None = None
#     client: str | None = None

#     class Config:
#         orm_mode = True




customer_list = [
    {"customer_id": "GR001", "Email": "sanjay@graytitude.com", "Phone": "+491604553094", "Name": "Sanjay"},
    {"customer_id": "GR002", "Email": "get.tushar.shinde@gmail.com", "Phone": "+919404434273", "Name": "Tushar"},
    {"customer_id": "GR003", "Email": "nitish@vaaniresearch.com", "Phone": "+917055888820", "Name": "Nitish"},
    {"customer_id": "GR004", "Email": "rajeev@graytitude.com", "Phone": "+917055888820", "Name": "Rajeev"},
    {"customer_id": "GR005", "Email": "will@graytitude.com", "Phone": "+917055888820", "Name": "Will"},
    {"customer_id": "GR006", "Email": "vaibhs52@gmail.com", "Phone": "+917568558767", "Name": "Rakesh"},
]

@app.get("/test")
async def test():
    return {"message": "Hello World"}


@app.post("/api/customer_exists/") 
async def check_customer(request: Request):
    raw_body = await request.json()
    print(f"Desbugging: ", raw_body)
    customer_id = (raw_body['args']['customer_id']).upper() if 'args' in raw_body and 'customer_id' in raw_body['args'] else raw_body['customer_id'].upper()
    print(customer_id.upper())

    if not customer_id:
        return {"exists": False, "response": "Missing customer ID. Please provide a valid one."}

    customer = next((c for c in customer_list if c["customer_id"] == customer_id), None)

    if customer:
        return {
            "exists": True,
            "Email": customer["Email"],
            "Name": customer["Name"],
            "Phone_number": customer["Phone"],
            "response": f"Customer found. The email is {customer['Email']} and the phone number is {customer['Phone']}."
        }
    else:
        return {"exists": False, "response": "Customer not found. Please provide a valid customer ID."}



@app.post("/api/customer_exists_2/") 
async def check_customer(request: Request):
    return f"Customer found. The email is nitish@gmail.com and the phone number is 123456."

@app.post("/api/get_calender_details/{event_id}")
async def get_calender_details(event_id: str, request: Request):

    raw_body = await request.json()
    start_time = raw_body['start_time']
    end_time = raw_body['end_time']
    url = "https://api.cal.com/v1/slots"
    
    querystring = {"apiKey":cal_api_key,
                   "eventTypeId":event_id,
                   "startTime":start_time,
                   "endTime":end_time}
    
    response = requests.request("GET", url, params=querystring)
    # print(response.text)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to fetch calendar details."}



#Have to make changes in these below functions.

@app.post("/api/confirm_appointment/")
async def confirm_appointment(request: Request):
    raw_body = await request.json()
    #We will make the cal.com call here
    print(raw_body)
    return {"message": "Appointment confirmed."}

@app.post("/api/update_customer_booking/")
async def update_customer_booking(request: Request):
    raw_body = await request.json()
    #We will make the cal.com call here
    print(raw_body)
    return {"message": "Booking updated successfully."}

@app.post("/api/get_customer_booking/")
async def get_customer_booking(request: Request):
    raw_body = await request.json()
    #We will make the cal.com call here
    print(raw_body)
    return {"message": "Booking fetched successfully."}

@app.post("/api/cancel_customer_booking/")
async def cancel_customer_booking(request: Request):
    raw_body = await request.json()
    #We will make the cal.com call here
    print(raw_body)
    return {"message": "Booking cancelled successfully."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)