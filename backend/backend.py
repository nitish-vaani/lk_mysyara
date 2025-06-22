#Fastapi server
#Need amazon rdbms server, have to design it as well, Make sure that the db can be altered/updted later with new columns.
#Need login with security
#Need a dashboard for admin which will show a high level data for the client.
    # Like Total number of calls, Calls picked, Lead generated
#Need a dashboard for all call history, which will show the call history for the client.
    # This will include the call time, duration, agent name, call status etc. Will be updated accordingly.
    # Each call will have a unique id, which can be used to track the transcript, summary and the entities extracted.
#The dashboard should be able to filter the data based on date, time, number etc.
#Should have an export button for selected data in csv format.
#Keep the code clean and modular, so that it can be easily extended in the future.
#Need apis. Frontend will be developed later.
#Need webhook to update db. I am storing call data in redis. So, I will need a webhook to update the db with the call data.
#Make sure that the webhook can be called with any sort of data, so that it can be used for other purposes.