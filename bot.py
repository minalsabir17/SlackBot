import os
import time
import threading
import requests
import json
import praw
from dotenv import dotenv_values
from queue import Queue

# --- CONFIGURATION ---
# Load environment variables from a .env file for security
try:
    config = dotenv_values(".env")
    SLACK_WEBHOOK_URL = config['SLACK_WEBHOOK_URL']
    REDDIT_CLIENT_ID = config['REDDIT_CLIENT_ID']
    REDDIT_CLIENT_SECRET = config['REDDIT_CLIENT_SECRET']
    REDDIT_USER_AGENT = config.get('REDDIT_USER_AGENT', 'Reddit Scraper 1.0')
except KeyError as e:
    print(f"Error: Missing environment variable {e}. Please check your .env file.")
    exit(1)

# --- CONSTANTS ---
# The subreddit and keywords you want to monitor
SUBREDDIT_TO_MONITOR = "jerseycity"
KEYWORDS_TO_MONITOR = [
    # Mayoral-race names & handles
    "Mussab Ali", "Ali2025", "#Ali2025", "Jim McGreevey", "McGreevey",
    "Bill O’Dea", "O’Dea", "James Solomon", "Solomon", "Joyce Watterman",
    "Watterman", "Flash Gordon", "Steven Fulop", "Fulop",

    # Current City-Council members (incumbents)
    "Daniel Rivera", "Rivera", "Amy DeGise", "DeGise", "Denise Ridley",
    "Ridley", "Maureen Hulings", "Hulings", "Richard Boggiano", "Boggiano",
    "Yousef Saleh", "Saleh", "Frank Gilmore", "Gilmore",

    # Declared or reported Council candidates (2025 cycle)
    "Tina Nalls", "Nalls", "Jennise Sarmiento", "Sarmiento",
    "Meredith Burns", "Burns", "Israel Nieves", "Nieves",
    "Kristen Zadroga-Hart", "Zadroga-Hart", "Saundra Robinson Green",
    "Robinson Green", "Rolando Lavarro", "Lavarro", "Mamta Singh", "Singh",
    "Michael Griffin", "Griffin", "Rev Tami Weaver-Henry", "Weaver-Henry",
    "Kenny Reyes", "Reyes", "Dave Carment", "Carment", "Brandi Warren",
    "Warren", "Ira Guilford", "Guilford", "Efrain Orleans", "Orleans",
    "Tom Zuppa", "Zuppa", "Shahab Khan", "Khan", "Catherine Healy", "Healy",
    "Ryan Baylock", "Baylock", "Gloria Walton", "Walton",

    # Key bodies & organizations
    "Jersey City Council", "HCDO", "Hudson County Democratic Organization",
    "Hudson County Board of Commissioners", "Jersey City BOE",
    "JC Redevelopment Agency", "NJ ELEC", "machine politics", "county line",

    # High-salience local issues & policy terms
    "rent control", "rent stabilization", "property-tax revaluation", "Reval",
    "affordable housing", "Inclusionary Zoning", "IZO", "Liberty State Park",
    "Caven Point", "PATH extension", "Jersey City–Newark PATH", "Vision Zero",
    "bike lanes", "short-term rentals", "Airbnb ordinance", "public safety",
    "police funding", "gun violence", "cannabis dispensary",
    "flooding", "stormwater fee", "Resiliency Plan", "Jersey City Greenway",
    "school funding", "state aid cuts",

    # Election mechanics & GOTV terms
    "vote by mail", "VBM", "early voting", "sample ballot", "polling place",
    "provisional ballot", "runoff election", "campaign finance report",
    "JCVotes 2025", "#JCVotes2025"
]
# How often to check for new items (in seconds)
FETCH_INTERVAL = 60
# How many recent posts to scan
SUBMISSION_LIMIT = 25 

# --- GLOBAL SHARED RESOURCES ---
# A thread-safe queue to hold items (posts or comments) waiting to be sent to Slack
items_queue = Queue()
# Sets to keep track of item IDs we've already processed to avoid duplicates
seen_submission_ids = set()
seen_comment_ids = set()
# An event to signal threads to stop running gracefully
stop_event = threading.Event()

# --- REDDIT API SETUP ---
try:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    print(f"Authenticated with Reddit as: {reddit.user.me()} (Read-Only Mode)")
except Exception as e:
    print(f"Failed to authenticate with Reddit: {e}")
    exit(1)


def reddit_item_producer():
    """
    Fetches new submissions and comments from a subreddit that match keywords
    and adds them to a queue.
    """
    print(f"[Producer] Starting to monitor r/{SUBREDDIT_TO_MONITOR} for keywords...")
    while not stop_event.is_set():
        try:
            subreddit = reddit.subreddit(SUBREDDIT_TO_MONITOR)
            print(f"[Producer] Fetching latest {SUBMISSION_LIMIT} submissions to scan...")
            
            for submission in subreddit.new(limit=SUBMISSION_LIMIT):
                # 1. Check the submission (post) itself
                if submission.id not in seen_submission_ids:
                    submission_text = submission.title + " " + submission.selftext
                    if any(keyword.lower() in submission_text.lower() for keyword in KEYWORDS_TO_MONITOR):
                        print(f"[Producer] Found relevant new post {submission.id}: '{submission.title}'.")
                        items_queue.put({'type': 'submission', 'data': submission})
                        seen_submission_ids.add(submission.id)
                
                # 2. Check the comments within the submission
                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    if comment.id not in seen_comment_ids:
                        if any(keyword.lower() in comment.body.lower() for keyword in KEYWORDS_TO_MONITOR):
                            print(f"[Producer] Found relevant new comment {comment.id} in post '{submission.title}'.")
                            items_queue.put({'type': 'comment', 'data': comment})
                            seen_comment_ids.add(comment.id)
            
            print("[Producer] Finished scan. Waiting for next interval.")
            stop_event.wait(FETCH_INTERVAL)

        except Exception as e:
            print(f"[Producer] An error occurred: {e}")
            stop_event.wait(FETCH_INTERVAL)

def slack_item_consumer():
    """
    Consumes items (posts/comments) from the queue and posts them to Slack.
    """
    print("[Consumer] Starting to send items to Slack...")
    while not stop_event.is_set():
        try:
            item = items_queue.get(timeout=1)
            item_type = item['type']
            data = item['data']
            message_payload = {}

            if item_type == 'submission':
                message_payload = {
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"New relevant post in *r/{SUBREDDIT_TO_MONITOR}* by `/u/{data.author}`"
                            }
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*<{data.permalink}|{data.title}>*\n{data.selftext[:500]}{'...' if len(data.selftext) > 500 else ''}"
                            }
                        }
                    ]
                }
            elif item_type == 'comment':
                message_payload = {
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"New relevant comment in *r/{SUBREDDIT_TO_MONITOR}* by `/u/{data.author}`"
                            }
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": { "type": "mrkdwn", "text": data.body }
                        },
                        {
                            "type": "context",
                            "elements": [
                                { "type": "mrkdwn", "text": f"In post: *<{data.submission.permalink}|{data.submission.title}>*" }
                            ]
                        }
                    ]
                }

            if message_payload:
                response = requests.post(
                    SLACK_WEBHOOK_URL, 
                    data=json.dumps(message_payload),
                    headers={'Content-Type': 'application/json'}
                )
                if response.status_code == 200:
                    print(f"[Consumer] Successfully posted {item_type} {data.id} to Slack.")
                else:
                    print(f"[Consumer] Failed to post message: {response.status_code}, {response.text}")
            
            items_queue.task_done()

        except Exception:
            pass # Queue was empty, continue loop

def main():
    """Main function to start and manage the bot threads."""
    producer_thread = threading.Thread(target=reddit_item_producer)
    consumer_thread = threading.Thread(target=slack_item_consumer)

    producer_thread.start()
    consumer_thread.start()

    try:
        while producer_thread.is_alive() and consumer_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Shutdown signal received. Stopping threads...")
        stop_event.set()

    producer_thread.join()
    consumer_thread.join()
    print("[Main] All threads have been stopped. Exiting.")

if __name__ == "__main__":
    main()
