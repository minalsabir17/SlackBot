import os
from dotenv import dotenv_values
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler  
import threading
import requests
import json
from reddit_api_call import reddit_api_call_func
import praw
import pandas as pd
import numpy as np
import re


config = dotenv_values(".env")
SLACK_TOKEN = config['SLACK_TOKEN']
SLACK_APP_TOKEN = config['SLACK_APP_TOKEN']
WEBHOOK_URL = config['WEBHOOK_URL']

client_id = config['CLIENT_ID']
client_secret = config['CLIENT_SECRET']

user_agent = 'Reddit_Scrapper 1.0 by /u/Active_Break9385'

reddit = praw.Reddit(
 client_id='NA59w4_hCCHW0tjzde1Alg',
 client_secret='lDpXKHai-zypU6_fs1KB9c0oiQmF5g',
 user_agent=user_agent
)

last_comments_section = pd.DataFrame()
messages = pd.DataFrame()

searching_reddit = False
sending_message = False
semaphore = threading.Semaphore(1)


def slack_bot():
    semaphore.acquire()

    while(messages):
        message = messages.pop(0)

        response = requests.post(
        WEBHOOK_URL, 
        data=json.dumps(message), 
        headers={'Content-Type': 'application/json'})
    
        if response.status_code == 200:
            print('Message posted successfully')
        else:
            print(f'Failed to post message: {response.status_code}, {response.text}')
        
    
    semaphore.release()


def reddit_search():
    semaphore.acquire()
    if not last_comments_section:
        # get the difference, return the news
        pass 
    
    comments = reddit_api_call_func(reddit=reddit)

    while searching_reddit:
        message = {f"text":\
                'author: {comment.author}, body: {comment.body}'}
        
        pd.concat([messages, message], inplace=True)
    
    semaphore.release()
    


# Run the bot in a separate thread
t1 = threading.Thread(target=slack_bot)
t1.start()
