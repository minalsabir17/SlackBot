import os
from dotenv import dotenv_values
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler  

config = dotenv_values(".env")
SLACK_TOKEN = config['SLACK_TOKEN']
SLACK_APP_TOKEN = config['SLACK_APP_TOKEN']


app = App(token=SLACK_TOKEN)  

@app.message("hello")
def say_hello(message, say): 
    say(f"Hi <@{message['user']}>!")  

if __name__ == "__main__": 
    handler = SocketModeHandler(
        app, 
        SLACK_APP_TOKEN
    )
    handler.start()
