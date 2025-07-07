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

# Import the new keyterm analyzer
from keyterm_analyzer import KeytermAnalyzer, analyze_reddit_post, analyze_reddit_comment

# --- CONFIGURATION ---
# Load environment variables from a .env file for security
try:
    config = dotenv_values(".env")
    SLACK_WEBHOOK_URL = config['SLACK_WEBHOOK_URL']
    SLACK_BOT_TOKEN = config.get('SLACK_BOT_TOKEN')
    SLACK_APP_TOKEN = config.get('SLACK_APP_TOKEN')
    REDDIT_CLIENT_ID = config['REDDIT_CLIENT_ID']
    REDDIT_CLIENT_SECRET = config['REDDIT_CLIENT_SECRET']
    REDDIT_USER_AGENT = config.get('REDDIT_USER_AGENT', 'Reddit Scraper 1.0')
    OPENAI_API_KEY = config.get('OPENAI_API_KEY')
except KeyError as e:
    print(f"Error: Missing environment variable {e}. Please check your .env file.")
    exit(1)

# Initialize OpenAI client
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized for AI overviews.")
    except Exception as e:
        print(f"Warning: Could not initialize OpenAI client: {e}")

# Initialize Slack clients
slack_web_client = None
slack_socket_client = None

if SLACK_BOT_TOKEN and SLACK_APP_TOKEN:
    try:
        import ssl
        import certifi
        
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        slack_web_client = WebClient(token=SLACK_BOT_TOKEN, ssl=ssl_context)
        slack_socket_client = SocketModeClient(
            app_token=SLACK_APP_TOKEN,
            web_client=slack_web_client
        )
        print("Slack interactive clients initialized.")
    except Exception as e:
        print(f"Warning: Could not initialize Slack clients: {e}")

# Initialize Keyterm Analyzer
keyterm_analyzer = KeytermAnalyzer()
print("Keyterm analyzer initialized with database.")

# --- CONSTANTS ---
SUBREDDIT_TO_MONITOR = "jerseycity"
KEYWORDS_TO_MONITOR = [
    "Mussab Ali", "Ali2025", "#Ali2025", "Jim McGreevey", "McGreevey",
    "Bill O'Dea", "O'Dea", "James Solomon", "Solomon", "Joyce Watterman",
    "Watterman", "Flash Gordon", "Steven Fulop", "Fulop",
    "Daniel Rivera", "Rivera", "Amy DeGise", "DeGise", "Denise Ridley",
    "Ridley", "Maureen Hulings", "Hulings", "Richard Boggiano", "Boggiano",
    "Yousef Saleh", "Saleh", "Frank Gilmore", "Gilmore",
    "Tina Nalls", "Nalls", "Jennise Sarmiento", "Sarmiento",
    "Meredith Burns", "Burns", "Israel Nieves", "Nieves",
    "Kristen Zadroga-Hart", "Zadroga-Hart", "Saundra Robinson Green",
    "Robinson Green", "Rolando Lavarro", "Lavarro", "Mamta Singh", "Singh",
    "Michael Griffin", "Griffin", "Rev Tami Weaver-Henry", "Weaver-Henry",
    "Kenny Reyes", "Reyes", "Dave Carment", "Carment", "Brandi Warren",
    "Warren", "Ira Guilford", "Guilford", "Efrain Orleans", "Orleans",
    "Tom Zuppa", "Zuppa", "Shahab Khan", "Khan", "Catherine Healy", "Healy",
    "Ryan Baylock", "Baylock", "Gloria Walton", "Walton",
    "Jersey City Council", "HCDO", "Hudson County Democratic Organization",
    "Hudson County Board of Commissioners", "Jersey City BOE",
    "JC Redevelopment Agency", "NJ ELEC", "machine politics", "county line",
    "vote by mail", "VBM", "early voting", "sample ballot", "polling place",
    "provisional ballot", "runoff election", "campaign finance report"
]

FETCH_INTERVAL = 60
SUBMISSION_LIMIT = 25

# --- GLOBAL SHARED RESOURCES ---
items_queue = Queue()
seen_submission_ids = set()
seen_comment_ids = set()
stop_event = threading.Event()
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
    """Generate AI overview using OpenAI."""
    if not openai_client:
        return None
    
    try:
        prompt = f"""Please provide a comprehensive summary of this Reddit post about Jersey City politics:

**Title:** {title}

**Post Content:** {text}

Focus on the key political points, candidates mentioned, and main issues discussed."""

        if comments_data and len(comments_data) > 0:
            comments_text = "\n".join([f"- {comment}" for comment in comments_data[:10]])
            prompt += f"""

**Top Comments:**
{comments_text}

Please provide a well-structured response with the following sections:

**📋 Post Summary**
2-3 sentences covering the key political points, candidates mentioned, and main issues discussed.

**💬 Community Response** 
2-3 sentences about what people are saying in the comments."""
        else:
            prompt += """

Please provide:

**📋 Post Summary**
2-3 sentences covering the key political points, candidates mentioned, and main issues discussed."""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes local political content and community discussions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"[AI Overview] Error generating summary: {e}")
        return None

def fetch_reddit_comments(reddit_id, subreddit_name, max_comments=10):
    """Fetch comments from a Reddit post for analysis."""
    try:
        submission = reddit.submission(id=reddit_id)
        submission.comments.replace_more(limit=0)
        
        comments = []
        for comment in submission.comments.list()[:max_comments]:
            if (comment.__class__.__name__ == 'Comment' and
                hasattr(comment, 'body') and 
                hasattr(comment, 'author') and
                comment.author is not None and
                str(comment.body).strip() not in ['[deleted]', '[removed]'] and
                len(str(comment.body).strip()) > 20):
                comments.append(str(comment.body).strip())
        
        print(f"[Comment Fetch] Found {len(comments)} comments for post {reddit_id}")
        return comments
        
    except Exception as e:
        print(f"[Comment Fetch] Error fetching comments for {reddit_id}: {e}")
        return []

def format_ai_overview_markdown(ai_overview, comment_count):
    """Format AI overview with Slack blocks."""
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🤖 *AI Overview & Community Analysis*"
            }
        },
        {"type": "divider"}
    ]
    
    sections = ai_overview.split('\n\n')
    
    for section in sections:
        if section.strip():
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": section.strip()
                }
            })
    
    if comment_count > 0:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📊 _Analyzed {comment_count} community comments_"
                }
            ]
        })
    
    return blocks

def reddit_item_producer():
    """Enhanced producer that includes keyterm analysis."""
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
                        
                        # KEYTERM ANALYSIS: Analyze the post
                        try:
                            analyze_reddit_post(keyterm_analyzer, submission)
                            print(f"[Keyterm] Analyzed post {submission.id} for keyterms")
                        except Exception as e:
                            print(f"[Keyterm] Error analyzing post {submission.id}: {e}")
                        
                        items_queue.put({'type': 'submission', 'data': submission})
                        seen_submission_ids.add(submission.id)
                
                # 2. Check the comments within the submission
                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    if comment.id not in seen_comment_ids:
                        if any(keyword.lower() in comment.body.lower() for keyword in KEYWORDS_TO_MONITOR):
                            print(f"[Producer] Found relevant new comment {comment.id} in post '{submission.title}'.")
                            
                            # KEYTERM ANALYSIS: Analyze the comment
                            try:
                                analyze_reddit_comment(keyterm_analyzer, comment)
                                print(f"[Keyterm] Analyzed comment {comment.id} for keyterms")
                            except Exception as e:
                                print(f"[Keyterm] Error analyzing comment {comment.id}: {e}")
                            
                            items_queue.put({'type': 'comment', 'data': comment})
                            seen_comment_ids.add(comment.id)
            
            print("[Producer] Finished scan. Waiting for next interval.")
            stop_event.wait(FETCH_INTERVAL)

        except Exception as e:
            print(f"[Producer] An error occurred: {e}")
            stop_event.wait(FETCH_INTERVAL)

def slack_item_consumer():
    """Enhanced consumer that can handle keyterm analysis requests."""
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
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "📊 _Keyterms extracted and stored in database_ | 🤖 _React with :robot_face: for AI analysis_"
                                }
                            ]
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
                                { "type": "mrkdwn", "text": f"In post: *<https://reddit.com{data.submission.permalink}|{data.submission.title}>*" },
                                { "type": "mrkdwn", "text": "📊 _Keyterms extracted and stored in database_" }
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
                    
                    # Store metadata for reaction handling
                    if item_type == 'submission' and slack_web_client:
                        message_metadata[data.id] = {
                            'type': 'submission',
                            'title': data.title,
                            'selftext': data.selftext,
                            'permalink': data.permalink,
                            'author': str(data.author),
                            'reddit_id': data.id,
                            'subreddit': str(data.subreddit)
                        }
                else:
                    print(f"[Consumer] Failed to post message: {response.status_code}, {response.text}")
            
            items_queue.task_done()

        except Exception:
            pass

def handle_reaction_added(client: WebClient, event: dict):
    """Handle reaction_added events."""
    try:
        print(f"[Reaction Handler] Received reaction event: {event.get('reaction')} by user {event.get('user')}")
        
        # Check for robot emoji reaction (AI analysis)
        if event.get("reaction") == "robot_face":
            channel = event.get("item", {}).get("channel")
            timestamp = event.get("item", {}).get("ts")
            
            if not channel or not timestamp:
                return

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
                
                for block in message.get("blocks", []):
                    if block.get("type") == "section" and "text" in block:
                        message_text += block["text"].get("text", "")
                
                reddit_post_data = None
                for post_id, metadata in message_metadata.items():
                    if metadata["title"] in message_text or metadata["permalink"] in message_text:
                        reddit_post_data = metadata
                        break
                
                if reddit_post_data and openai_client:
                    comments = fetch_reddit_comments(
                        reddit_post_data['reddit_id'], 
                        reddit_post_data['subreddit']
                    )
                    
                    ai_overview = generate_ai_overview(
                        reddit_post_data["selftext"], 
                        reddit_post_data["title"],
                        comments_data=comments
                    )
                    
                    if ai_overview:
                        formatted_overview = format_ai_overview_markdown(ai_overview, len(comments))
                        
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=timestamp,
                            blocks=formatted_overview
                        )
                        print(f"[Reaction Handler] Posted AI overview for {reddit_post_data['title']}")
                        
            except Exception as e:
                print(f"[Reaction Handler] Error processing message: {e}")
        
        # Check for chart emoji reaction (keyterm analysis)
        elif event.get("reaction") == "chart_with_upwards_trend":
            channel = event.get("item", {}).get("channel")
            timestamp = event.get("item", {}).get("ts")
            
            if not channel or not timestamp:
                return
            
            try:
                # Generate keyterm analysis
                top_keyterms = keyterm_analyzer.get_top_keyterms(limit=10, days_back=7)
                
                if not top_keyterms.empty:
                    keyterm_text = "*📊 Top Keyterms (Last 7 Days)*\n\n"
                    for _, row in top_keyterms.head(10).iterrows():
                        keyterm_text += f"• *{row['term']}*: {row['total_frequency']} occurrences\n"
                    
                    # Get recent context for top term
                    if len(top_keyterms) > 0:
                        top_term = top_keyterms.iloc[0]['term']
                        context = keyterm_analyzer.get_keyterm_context(top_term, limit=2)
                        if context:
                            keyterm_text += f"\n*Recent context for '{top_term}':*\n"
                            for ctx in context[:2]:
                                keyterm_text += f"• _{ctx['context'][:100]}..._\n"
                    
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=timestamp,
                        text=keyterm_text
                    )
                    print("[Reaction Handler] Posted keyterm analysis")
                else:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=timestamp,
                        text="📊 No keyterm data available yet. Keep monitoring!"
                    )
                    
            except Exception as e:
                print(f"[Reaction Handler] Error generating keyterm analysis: {e}")
                
    except Exception as e:
        print(f"[Reaction Handler] Error handling reaction: {e}")

def slack_reaction_handler():
    """Handle Slack reactions in a separate thread."""
    if not slack_socket_client:
        print("[Reaction Handler] Slack socket client not available. Skipping reaction handler.")
        return
    
    def process_events(client: SocketModeClient, req: SocketModeRequest):
        if req.type == "events_api":
            event = req.payload["event"]
            if event.get("type") == "reaction_added":
                handle_reaction_added(slack_web_client, event)
        
        # Acknowledge the request
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

    slack_socket_client.socket_mode_request_listeners.append(process_events)
    slack_socket_client.connect()
    print("[Reaction Handler] Connected to Slack socket mode for reactions")

def generate_daily_keyterm_report():
    """Generate and optionally send daily keyterm report."""
    try:
        top_keyterms = keyterm_analyzer.get_top_keyterms(limit=20, days_back=1)
        
        if not top_keyterms.empty:
            report_text = "*📊 Daily Keyterm Report*\n\n"
            report_text += f"*Top keyterms from the last 24 hours:*\n"
            
            for _, row in top_keyterms.head(15).iterrows():
                report_text += f"• *{row['term']}*: {row['total_frequency']} occurrences\n"
            
            # You can send this to Slack or save it to a file
            print("\n" + "="*50)
            print("DAILY KEYTERM REPORT")
            print("="*50)
            print(report_text)
            print("="*50)
            
        else:
            print("No keyterms found for today's report")
            
    except Exception as e:
        print(f"Error generating daily report: {e}")

def main():
    """Main function to run the enhanced bot."""
    print("Starting enhanced Jersey City Politics Reddit Bot with Keyterm Analysis...")
    
    # Start the threads
    producer_thread = threading.Thread(target=reddit_item_producer, daemon=True)
    consumer_thread = threading.Thread(target=slack_item_consumer, daemon=True)
    reaction_thread = threading.Thread(target=slack_reaction_handler, daemon=True)
    
    producer_thread.start()
    consumer_thread.start()
    
    if slack_socket_client:
        reaction_thread.start()
    
    print("Bot started! Monitoring for Reddit posts and extracting keyterms...")
    print("React with 🤖 for AI analysis, 📈 for keyterm analysis")
    print("Available commands:")
    print("  - Check database for keyterms")
    print("  - Generate visualizations")
    print("  - Export data to CSV")
    
    try:
        # Generate initial report
        generate_daily_keyterm_report()
        
        # Run indefinitely
        while True:
            time.sleep(300)  # Check every 5 minutes
            
            # Generate daily report every hour (optional)
            if time.time() % 3600 < 300:  # Within 5 minutes of hour mark
                generate_daily_keyterm_report()
                
    except KeyboardInterrupt:
        print("\nShutting down bot...")
        stop_event.set()
        
        # Wait for threads to finish
        producer_thread.join(timeout=5)
        consumer_thread.join(timeout=5)
        
        if slack_socket_client:
            reaction_thread.join(timeout=5)
        
        print("Bot stopped.")

if __name__ == "__main__":
    main() 