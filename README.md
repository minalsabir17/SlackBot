# Jersey City Politics SlackBot

A bot that monitors the Jersey City subreddit for posts and comments related to local politics and sends relevant content to Slack with AI-powered overviews for large posts.

## Features

- **Keyword Monitoring**: Tracks posts and comments containing keywords related to Jersey City politics, including:
  - Mayoral candidates and city council members
  - Local organizations and political bodies
  - Key policy issues (rent control, affordable housing, etc.)
  - Election-related terms

- **Reaction-Based AI Overviews**: Generate AI summaries by reacting to bot messages with 🤖 robot emoji
- **Real-time Notifications**: Sends formatted messages to Slack via webhooks
- **Duplicate Prevention**: Tracks processed posts and comments to avoid spam

## Setup

### Prerequisites

1. Python 3.7+
2. Reddit API credentials
3. Slack webhook URL
4. OpenAI API key (optional, for AI overviews)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   SLACK_BOT_TOKEN=xoxb-your-bot-token-here  # For reading reactions
   SLACK_APP_TOKEN=xapp-your-app-token-here  # For socket mode
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=Reddit Scraper 1.0
   OPENAI_API_KEY=your_openai_api_key_here  # Optional
   ```

### Slack App Setup

For reaction-based AI overviews, you need to create a Slack app with the following:

1. **Bot Token Scopes**: `chat:write`, `reactions:read`, `channels:history`
2. **Event Subscriptions**: Enable and subscribe to `reaction_added` event
3. **Socket Mode**: Enable for real-time events

### Configuration

- **FETCH_INTERVAL**: How often to check for new posts (default: 60 seconds)
- **SUBMISSION_LIMIT**: Number of recent posts to scan (default: 25)

## Usage

Run the bot:
```bash
python bot.py
```

The bot will:
1. Monitor r/jerseycity for new posts and comments
2. Check content against political keywords
3. Generate AI overviews for large posts (if OpenAI is configured)
4. Send formatted messages to your Slack channel

## AI Overview Feature

The bot now supports **reaction-based AI overviews**:

1. When the bot posts a Reddit message to Slack
2. React to the message with the 🤖 robot emoji
3. The bot generates a 2-3 sentence AI summary and posts it as a thread reply
4. Summaries focus on key political points, candidates mentioned, and main issues

**Requirements**:
- OpenAI API key (for generating summaries)
- Slack Bot Token and App Token (for reading reactions)
- Proper Slack app permissions and event subscriptions

**Note**: If OpenAI or Slack interactive features aren't configured, the bot will function normally as a basic Reddit monitor.

## Architecture

The bot uses a producer-consumer pattern:
- **Producer thread**: Fetches new Reddit content
- **Consumer thread**: Processes queue and sends to Slack
- **Thread-safe queue**: Manages communication between threads