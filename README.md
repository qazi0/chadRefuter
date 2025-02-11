# ChadRefuter

## Description
ChadRefuter is an AI-powered Reddit bot designed to engage in meaningful discussions and debates. Using a local Large Language Model (LLM), it automatically processes posts, generates well-reasoned responses, and maintains ongoing conversations while adhering to Reddit's best practices and rate limits.

## Features
### Core Functionality
- Automated Reddit monitoring and response generation
- Local LLM integration for intelligent response processing
- Multi-threaded conversation management
- Comprehensive logging and error handling

### Specific Capabilities
- **Subreddit Monitoring**: Scans configured subreddits every 60 seconds for new posts
- **Intelligent Response Generation**: Processes posts through a local LLM for contextual responses
- **Conversation Threading**: 
  - Monitors and responds to replies every 5 minutes
  - Maintains up to 5 concurrent active conversations
  - Tracks conversation context for coherent dialogue
- **Rate Limiting & Safety**:
  - Implements Reddit API rate limiting
  - Graceful error handling and recovery
  - State persistence for conversation tracking
- **Monitoring & Logging**:
  - Structured logging for operational monitoring
  - Error tracking and reporting
  - Performance metrics collection

## Technical Stack
- Python 3.8+
- PRAW (Python Reddit API Wrapper)
- Local LLM integration
- Structured logging with Python's logging module

## Installation
To get started with ChadRefuter, follow these steps:

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/chadrefuter.git
   cd chadrefuter
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables
   ```bash
   cp .env.example .env
   # Edit .env with your Reddit API credentials and configuration
   ```

## Usage
1. Start the bot:
   ```bash
   python src/main.py
   ```

2. Monitor the logs:
   ```bash
   tail -f logs/chadrefuter.log
   ```

### Configuration
Key configuration options in `.env`:
```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_bot_username
SUBREDDIT_NAME=target_subreddit
MAX_CONVERSATIONS=5
SCAN_INTERVAL=60
REPLY_CHECK_INTERVAL=300
```
