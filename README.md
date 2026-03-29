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

---

## Running from an EC2 Server

Reddit blocks EC2 IP ranges on `www.reddit.com`. Here's what works and what doesn't.

### What works: oauth.reddit.com with a Bearer token

All posting and monitoring goes through `oauth.reddit.com` instead of `www.reddit.com`. This endpoint is not blocked and accepts a `token_v2` JWT as a Bearer token:

```python
req.add_header("Authorization", f"Bearer {TOKEN_V2}")
req.add_header("User-Agent", "your-bot/1.0")
# POST https://oauth.reddit.com/api/submit
# GET  https://oauth.reddit.com/comments/{post_id}
```

See `reddit_playwright.py` for posting and `monitor.py` for monitoring.

### Token management

`token_v2` is a 24h JWT stored as an HttpOnly cookie. It cannot be read via `document.cookie`. To get a fresh token:

**Manually (bookmarklet):**
1. Go to reddit.com while logged in
2. Click the bookmarklet below — it patches `window.fetch` to intercept outgoing Bearer tokens
3. Scroll the page to trigger a background API call
4. Click the bookmarklet again to see the captured token

```javascript
javascript:(function(){if(window._ti){if(window._ct){prompt('token_v2:',window._ct);}else{alert('No token captured yet.\nScroll the page then click again.');}return;}window._ti=true;window._ct=null;var of=window.fetch;window.fetch=function(){var a=arguments,o=a[1]||{},h=o.headers||{},auth;if(typeof h.get==='function')auth=h.get('Authorization');else auth=h['Authorization']||h['authorization']||'';if(auth&&auth.startsWith('Bearer '))window._ct=auth.slice(7);return of.apply(this,a);};var ox=XMLHttpRequest.prototype.setRequestHeader;XMLHttpRequest.prototype.setRequestHeader=function(n,v){if(n.toLowerCase()==='authorization'&&v&&v.startsWith('Bearer '))window._ct=v.slice(7);return ox.apply(this,arguments);};alert('Armed! Now scroll the page to trigger API calls, then click again.');})();
```

Store the token as `REDDIT_TOKEN_V2` in your `.env`.

**Note:** `reddit_session` is a 6-month JWT (also HttpOnly) that could theoretically be used to refresh `token_v2` server-side, but Reddit blocks authenticated page loads from EC2 and residential proxy IPs alike — so server-side refresh is not currently feasible.

### What didn't work

| Approach | Why it failed |
|---|---|
| `www.reddit.com` direct | EC2 IP blocked (403) |
| Webshare residential proxy | Blocked for authenticated requests; `www.reddit.com` still 403s |
| 2captcha anti-captcha | Reddit uses Google reCAPTCHA Enterprise (behavioral scoring) — returns `ERROR_CAPTCHA_UNSOLVABLE` |
| Playwright browser automation | Reddit detects EC2/proxy and blocks login |
| Public JSON API (`*.json`) | Blocked from EC2 even without auth |

### Posting to subreddits with karma restrictions

New accounts with low karma (<100) are blocked from posting to large subreddits (e.g. r/LocalLLaMA). Strategy:
- Start with lower-barrier subreddits: r/artificial, r/PromptEngineering, r/MachineLearning, r/SideProject
- Some subreddits require post flair — fetch available flairs via:
  ```
  GET https://oauth.reddit.com/r/{subreddit}/api/link_flair_v2
  ```
- Each upvote builds karma toward higher-karma subreddits

## Monitoring: monitor.py

`monitor.py` fetches scores and top comments for a set of posts and reports to Slack. Runs daily via cron.

```bash
SLACK_BOT_TOKEN=... REDDIT_TOKEN_V2=... python monitor.py
```

Uses `oauth.reddit.com` to avoid EC2 IP blocks. Configure target posts and Slack channel inside the file.

Cron (9am UTC daily):
```
0 9 * * * export SLACK_BOT_TOKEN=$(grep SLACK_BOT_TOKEN /path/to/.env | cut -d= -f2) && export REDDIT_TOKEN_V2=$(grep REDDIT_TOKEN_V2 /path/to/.env | cut -d= -f2) && python /path/to/reddit-tool/monitor.py
```
