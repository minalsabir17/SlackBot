import os
import time
import threading
import requests
import json
import praw
from dotenv import dotenv_values
from queue import Queue
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

# --- CONFIGURATION ---
# Load environment variables from a .env file for security
try:
    config = dotenv_values(".env")
    SLACK_WEBHOOK_URL = config['SLACK_WEBHOOK_URL']
    SLACK_BOT_TOKEN = config.get('SLACK_BOT_TOKEN')  # For reading reactions
    SLACK_APP_TOKEN = config.get('SLACK_APP_TOKEN')  # For socket mode
    REDDIT_CLIENT_ID = config['REDDIT_CLIENT_ID']
    REDDIT_CLIENT_SECRET = config['REDDIT_CLIENT_SECRET']
    REDDIT_USER_AGENT = config.get('REDDIT_USER_AGENT', 'Reddit Scraper 1.0')
    OPENAI_API_KEY = config.get('OPENAI_API_KEY')
except KeyError as e:
    print(f"Error: Missing environment variable {e}. Please check your .env file.")
    exit(1)

# Initialize OpenAI client (optional for AI overviews)
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized for AI overviews.")
    except Exception as e:
        print(f"Warning: Could not initialize OpenAI client: {e}")
        print("AI overviews will be disabled.")
else:
    print("No OpenAI API key found. AI overviews will be disabled.")

# Initialize Slack clients for reaction handling
slack_web_client = None
slack_socket_client = None

print(f"[DEBUG] SLACK_BOT_TOKEN exists: {bool(SLACK_BOT_TOKEN)}")
print(f"[DEBUG] SLACK_APP_TOKEN exists: {bool(SLACK_APP_TOKEN)}")

if SLACK_BOT_TOKEN and SLACK_APP_TOKEN:
    try:
        import ssl
        import certifi
        
        # Create SSL context for Slack connections
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        print("[DEBUG] Creating Slack WebClient...")
        slack_web_client = WebClient(token=SLACK_BOT_TOKEN, ssl=ssl_context)
        
        print("[DEBUG] Creating Slack SocketModeClient...")
        slack_socket_client = SocketModeClient(
            app_token=SLACK_APP_TOKEN,
            web_client=slack_web_client
        )
        print("Slack interactive clients initialized for reaction handling.")
    except Exception as e:
        print(f"Warning: Could not initialize Slack clients: {e}")
        print("Reaction-based AI overviews will be disabled.")
        slack_web_client = None
        slack_socket_client = None
else:
    print("Slack bot/app tokens not found. Reaction-based AI overviews will be disabled.")

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
# Dictionary to store message metadata for reaction handling
message_metadata = {}

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


def generate_ai_overview(text, title="", comments_data=None):
    """
    Generate an AI overview/summary of the given text and comments using OpenAI.
    Returns the summary or None if AI is not available.
    """
    if not openai_client:
        return None
    
    try:
        # Prepare the base prompt
        prompt = f"""Please provide a comprehensive summary of this Reddit post about Jersey City politics:

**Title:** {title}

**Post Content:** {text}

Focus on the key political points, candidates mentioned, and main issues discussed."""

        # Add comments analysis if available
        if comments_data and len(comments_data) > 0:
            comments_text = "\n".join([f"- {comment}" for comment in comments_data[:10]])  # Limit to top 10 comments
            prompt += f"""

**Top Comments:**
{comments_text}

Please provide:
1. **Post Summary** (2-3 sentences): Key points from the original post
2. **Community Response** (2-3 sentences): What people are saying in the comments - common themes, reactions, additional insights, or disagreements"""
        else:
            prompt += "\n\nProvide a 2-3 sentence summary of the key political points."

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes local political content and community discussions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,  # Increased for comment analysis
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"[AI Overview] Error generating summary: {e}")
        return None


def fetch_reddit_comments(reddit_id, subreddit_name, max_comments=10):
    """
    Fetch comments from a Reddit post for analysis.
    Returns a list of comment texts.
    """
    try:
        # Get the submission from Reddit
        submission = reddit.submission(id=reddit_id)
        
        # Fetch comments (replace "load more" with actual comments)
        submission.comments.replace_more(limit=0)
        
        comments = []
        for comment in submission.comments.list()[:max_comments]:
            # Skip MoreComments objects and only process actual Comment objects
            if (comment.__class__.__name__ == 'Comment' and
                hasattr(comment, 'body') and 
                hasattr(comment, 'author') and
                comment.author is not None and  # Skip deleted accounts
                str(comment.body).strip() not in ['[deleted]', '[removed]'] and
                len(str(comment.body).strip()) > 20):  # Ignore very short comments
                comments.append(str(comment.body).strip())
        
        print(f"[Comment Fetch] Found {len(comments)} comments for post {reddit_id}")
        return comments
        
    except Exception as e:
        print(f"[Comment Fetch] Error fetching comments for {reddit_id}: {e}")
        return []


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
                                "text": f"*<https://reddit.com{data.permalink}|{data.title}>*\n{data.selftext[:500]}{'...' if len(data.selftext) > 500 else ''}"
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
                                { "type": "mrkdwn", "text": f"In post: *<https://reddit.com{data.submission.permalink}|{data.submission.title}>*" }
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
                    
                    # Store metadata for reaction handling (only for submissions)
                    if item_type == 'submission' and slack_web_client:
                        # Note: We can't get the message timestamp from webhook response
                        # Store basic info for potential reaction handling
                        message_metadata[data.id] = {
                            'type': 'submission',
                            'title': data.title,
                            'selftext': data.selftext,
                            'permalink': data.permalink,
                            'author': str(data.author),
                            'reddit_id': data.id,  # Store Reddit post ID for comment fetching
                            'subreddit': str(data.subreddit)
                        }
                else:
                    print(f"[Consumer] Failed to post message: {response.status_code}, {response.text}")
            
            items_queue.task_done()

        except Exception:
            pass # Queue was empty, continue loop

def handle_reaction_added(client: WebClient, event: dict):
    """
    Handle reaction_added events to trigger AI overviews when robot emoji is used.
    """
    try:
        print(f"[Reaction Handler] Received reaction event: {event.get('reaction')} by user {event.get('user')}")
        
        # Check if it's a robot emoji reaction
        if event.get("reaction") == "robot_face":
            channel = event.get("item", {}).get("channel")
            timestamp = event.get("item", {}).get("ts")
            
            if not channel or not timestamp:
                return
            
            # Get the message content to extract Reddit post ID
            try:
                message_result = client.conversations_history(
                    channel=channel,
                    latest=timestamp,
                    limit=1,
                    inclusive=True
                )
                
                if not message_result["ok"] or not message_result["messages"]:
                    return
                
                message = message_result["messages"][0]
                message_text = ""
                
                # Extract text from blocks
                for block in message.get("blocks", []):
                    if block.get("type") == "section" and "text" in block:
                        message_text += block["text"].get("text", "")
                
                # Try to find Reddit post ID or permalink in the message
                reddit_post_data = None
                for post_id, metadata in message_metadata.items():
                    if metadata["title"] in message_text or metadata["permalink"] in message_text:
                        reddit_post_data = metadata
                        break
                
                if reddit_post_data and openai_client:
                    # Fetch comments for analysis
                    print(f"[Reaction Handler] Fetching comments for post {reddit_post_data['reddit_id']}...")
                    comments = fetch_reddit_comments(
                        reddit_post_data['reddit_id'], 
                        reddit_post_data['subreddit']
                    )
                    
                    # Generate AI overview with comments
                    ai_overview = generate_ai_overview(
                        reddit_post_data["selftext"], 
                        reddit_post_data["title"],
                        comments_data=comments
                    )
                    
                    if ai_overview:
                        # Post AI overview as a thread reply
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=timestamp,
                            text=f"🤖 *AI Overview:*\n{ai_overview}"
                        )
                        print(f"[Reaction Handler] Posted AI overview for {reddit_post_data['title']} with {len(comments)} comments")
                    else:
                        print("[Reaction Handler] Failed to generate AI overview")
                else:
                    print("[Reaction Handler] Could not find matching Reddit post or OpenAI not available")
                        
            except Exception as e:
                print(f"[Reaction Handler] Error processing message: {e}")
                
    except Exception as e:
        print(f"[Reaction Handler] Error handling reaction: {e}")

def slack_reaction_handler():
    """
    Handle Slack events including reactions using Socket Mode.
    """
    print(f"[Reaction Handler] Socket client status: {slack_socket_client}")
    
    if not slack_socket_client:
        print("[Reaction Handler] Slack Socket Mode not available. Skipping reaction handling.")
        return
    
    print("[Reaction Handler] Socket client is available, setting up event handler...")
    
    def process_events(client: SocketModeClient, req: SocketModeRequest):
        print(f"[Reaction Handler] Received socket event: {req.type}")
        
        if req.type == "events_api":
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
            
            # Handle the event
            event = req.payload.get("event", {})
            print(f"[Reaction Handler] Event type: {event.get('type')}")
            
            if event.get("type") == "reaction_added":
                handle_reaction_added(slack_web_client, event)
            else:
                print(f"[Reaction Handler] Ignoring event type: {event.get('type')}")
    
    slack_socket_client.socket_mode_request_listeners.append(process_events)
    
    print("[Reaction Handler] Starting Slack event listener...")
    try:
        print("[Reaction Handler] Attempting to connect to Slack...")
        slack_socket_client.connect()
        print("[Reaction Handler] Successfully connected to Slack Socket Mode!")
        
        # Keep the connection alive with periodic status
        connection_check_counter = 0
        while not stop_event.is_set():
            time.sleep(1)
            connection_check_counter += 1
            if connection_check_counter % 30 == 0:  # Every 30 seconds
                print(f"[Reaction Handler] Connection alive, waiting for events... ({connection_check_counter}s)")
    except Exception as e:
        print(f"[Reaction Handler] Error in socket mode: {e}")
        print("[Reaction Handler] Check your Slack app configuration and tokens.")
    finally:
        print("[Reaction Handler] Disconnecting from Slack...")
        slack_socket_client.disconnect()

def main():
    """Main function to start and manage the bot threads."""
    producer_thread = threading.Thread(target=reddit_item_producer)
    consumer_thread = threading.Thread(target=slack_item_consumer)
    
    # Start reaction handler if Slack interactive mode is available
    reaction_thread = None
    if slack_socket_client:
        reaction_thread = threading.Thread(target=slack_reaction_handler)

    producer_thread.start()
    consumer_thread.start()
    
    if reaction_thread:
        reaction_thread.start()
        print("[Main] Started reaction handler thread.")

    try:
        threads_to_monitor = [producer_thread, consumer_thread]
        if reaction_thread:
            threads_to_monitor.append(reaction_thread)
            
        while all(thread.is_alive() for thread in threads_to_monitor):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Shutdown signal received. Stopping threads...")
        stop_event.set()

    producer_thread.join()
    consumer_thread.join()
    if reaction_thread:
        reaction_thread.join()
    print("[Main] All threads have been stopped. Exiting.")

if __name__ == "__main__":
    main()
