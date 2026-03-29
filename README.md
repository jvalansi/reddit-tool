# reddit-tool

A CLI tool for validating project ideas on Reddit — search for pain points, post for feedback, and track engagement.

## Setup

1. Create a Reddit script app at https://www.reddit.com/prefs/apps
2. Add credentials to your `.env`:

```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
```

3. Install dependencies:

```bash
pip install praw
```

## Usage

### Search subreddits for pain points

```bash
python reddit_tool.py search --query "CV generator" --subreddits r/resumes,r/jobs --limit 10 --sort relevance
```

### Submit a post

```bash
python reddit_tool.py post --subreddit SideProject --title "Would you use a tool that auto-generates your CV?" --body "I'm building..."
```

### Collect feedback (comments on a post)

```bash
python reddit_tool.py get-comments --post-id abc123 --limit 50
```

### Check post engagement

```bash
python reddit_tool.py get-post --post-id abc123
```

## Workflow

1. **Search** relevant subreddits to find existing pain points and gauge demand
2. **Post** a question or problem description (no product pitch yet)
3. **Collect comments** to analyze feedback
4. If validated → build a landing page and link it in the thread

## Running from EC2

See [docs/ec2-setup.md](docs/ec2-setup.md) for notes on bypassing Reddit's EC2 IP blocks, token management, what approaches were tried, and the daily monitoring setup.
