# ChadRefuter

## Description
ChadRefuter is an AI-powered Reddit bot that leverages multiple LLM providers (Ollama, OpenAI, Anthropic, HuggingFace) to engage in discussions and debates. Using asynchronous processing and queues, it efficiently handles post scanning, response generation, and comment posting while strictly adhering to Reddit's API rate limits.

## Features

### Core Functionality
- Asynchronous post processing and comment management using `asyncio`
- Support for multiple LLM providers with easy switching
- SQLite database for post/comment tracking and persistence
- Comprehensive error handling and graceful shutdown
- Structured logging with both file and console output

### LLM Integration
- **Multiple Provider Support**:
  - Ollama (default, local deployment)
  - OpenAI (GPT-3.5/4)
  - Anthropic (Claude)
  - HuggingFace (hosted models)
- **Configurable Models**: Each provider supports custom model selection
- **Fallback Handling**: Graceful error handling for LLM failures

### Processing Architecture
- **Asynchronous Queues**:
  - Post Queue: Manages newly detected posts
  - Processing Queue: Handles LLM-generated responses
- **Rate Limiting**:
  - 120-second delay between comments
  - Automatic queue management
  - Reddit API compliance
- **Concurrent Operations**:
  - Parallel post scanning
  - Async response generation
  - Non-blocking comment posting

## Technical Stack
- Python 3.8+
- PRAW (Reddit API)
- `asyncio` for concurrent operations
- SQLite for persistence
- Multiple LLM provider SDKs

## Installation

1. Clone the repository:
   ``bash
   git clone https://github.com/yourusername/chadrefuter.git
   cd chadrefuter
   ``

2. Install dependencies:
   ``bash
   pip install -r requirements.txt
   ``

3. Configure environment:
   ``bash
   cp .env.example .env
   # Edit .env with your credentials
   ``

## Configuration

Required environment variables in `.env`:
``env
# Reddit API Credentials
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
USERNAME=your_bot_username
PASSWORD=your_bot_password
USER_AGENT=python:chadrefuter:v1.0 (by /u/your_username)

# Bot Configuration
SUBREDDIT=target_subreddit
SCAN_INTERVAL=60
REPLY_SCAN_INTERVAL=300
MAX_CONVERSATIONS=5
POSTS_FETCH_LIMIT=5
POST_CACHE_SIZE=1000

# LLM API Keys (Optional, based on provider)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
HUGGINGFACE_API_KEY=your_hf_key
``

## Usage

1. Start the bot with default Ollama provider:
   ``bash
   python src/bot.py
   ``

2. Use specific LLM provider:
   ``bash
   python src/bot.py --llm-provider openai --llm-model gpt-3.5-turbo
   ``

Available providers:
- `ollama` (default, uses `llama2:latest`)
- `openai` (default: `gpt-3.5-turbo`)
- `anthropic` (default: `claude-3-sonnet-20240229`)
- `huggingface` (default: `meta-llama/Llama-2-7b-chat-hf`)

3. Monitor logs:
   ``bash
   tail -f logs/reddit_bot_YYYYMMDD.log
   ``

## Architecture Details

### Asynchronous Processing Flow
1. **Post Scanner** (`scan_posts`):
   - Runs every `SCAN_INTERVAL` seconds
   - Fetches new posts using PRAW
   - Adds to `post_queue`

2. **Queue Processor** (`process_queue`):
   - Continuously monitors `post_queue`
   - Processes posts through LLM
   - Adds responses to `processing_queue`

3. **Comment Handler** (`comment_processor`):
   - Monitors `processing_queue`
   - Implements rate limiting
   - Posts comments to Reddit

### Database Schema
- **Posts Table**:
  - `post_id`: Reddit post ID
  - `subreddit`: Subreddit name
  - `title`: Post title
  - `post_text`: Post content
  - `author`: Post author
  - `timestamp`: Post creation time
  - `llm_response`: Generated response
  - `response_timestamp`: Response time

### Logging
- Structured logging with thread-safe handlers
- Separate console and file outputs
- Detailed debug information for LLM interactions
- Performance metrics and error tracking

## License
MIT License - see `LICENSE` for details
