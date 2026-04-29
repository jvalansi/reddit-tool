#!/usr/bin/env python3
"""
Reddit tool — post and monitor via Reddit API using a browser-extracted token_v2 JWT.
No API key approval needed. Token lasts ~24h; refresh by re-exporting from browser.

Usage:
  python reddit_playwright.py post --subreddit NAME --title TITLE --body TEXT
  python reddit_playwright.py get-comments --post-id ID [--limit N]
  python reddit_playwright.py get-post --post-id ID
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse

# ── Load env ──────────────────────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "..", "slack-claude-bot", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

TOKEN = os.environ.get("REDDIT_TOKEN_V2")
UA = "script:promptware-validator:v1.0 (by u/toothwry)"
_PROXY = os.environ.get("REDDIT_PROXY_URL", "")


def _make_opener():
    if not _PROXY:
        return urllib.request.build_opener()
    proxy_handler = urllib.request.ProxyHandler({"https": _PROXY, "http": _PROXY})
    return urllib.request.build_opener(proxy_handler)


def api(method, path, data=None):
    url = f"https://oauth.reddit.com{path}"
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", UA)
    if body:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    opener = _make_opener()
    with opener.open(req, timeout=30) as r:
        return json.loads(r.read())


def cmd_search(args):
    if not TOKEN:
        print(json.dumps({"error": "REDDIT_TOKEN_V2 not set."}))
        sys.exit(1)

    subreddits = [s.strip().lstrip("r/") for s in args.subreddits.split(",")] if args.subreddits else ["all"]
    results = []

    for sub in subreddits:
        after = ""
        while len(results) < args.limit:
            path = f"/r/{sub}/search" if sub != "all" else "/search"
            params = f"q={urllib.parse.quote(args.query)}&sort={args.sort}&restrict_sr=1&limit=25"
            if after:
                params += f"&after={after}"
            data = api("GET", f"{path}?{params}")
            children = data.get("data", {}).get("children", [])
            if not children:
                break
            for child in children:
                if len(results) >= args.limit:
                    break
                d = child["data"]
                results.append({
                    "id": d["id"],
                    "subreddit": d["subreddit"],
                    "title": d["title"],
                    "score": d["score"],
                    "num_comments": d["num_comments"],
                    "url": f"https://www.reddit.com{d['permalink']}",
                    "selftext": d.get("selftext", "")[:500],
                    "created_utc": int(d["created_utc"]),
                })
            after = data.get("data", {}).get("after") or ""
            if not after:
                break

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_post(args):
    from playwright.sync_api import sync_playwright
    import re as _re
    sys.path.insert(0, os.path.dirname(__file__))
    from refresh_token import load_env, start_proxy

    env = load_env()
    user_token = env.get("REDDIT_USER_TOKEN") or env.get("REDDIT_TOKEN_V2")
    required = ["REDDIT_SESSION", "REDDIT_CSRF_TOKEN", "REDDIT_LOID"]
    missing = [k for k in required if not env.get(k)]
    if missing or not user_token:
        print(json.dumps({"error": f"Missing env vars: {missing or ['REDDIT_USER_TOKEN']}"}))
        sys.exit(1)

    proxy_url = env.get("REDDIT_PROXY_URL", "")
    proxy_thread = start_proxy(proxy_url) if proxy_url else None
    if proxy_thread:
        import time; time.sleep(0.5)

    subreddit = args.subreddit.lstrip("r/")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
                proxy={"server": "http://127.0.0.1:18899"} if proxy_url else None,
            )
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            ctx.add_cookies([
                {"name": "token_v2",       "value": user_token,               "domain": ".reddit.com", "path": "/"},
                {"name": "reddit_session", "value": env["REDDIT_SESSION"],    "domain": ".reddit.com", "path": "/", "httpOnly": True, "secure": True},
                {"name": "csrf_token",     "value": env["REDDIT_CSRF_TOKEN"], "domain": ".reddit.com", "path": "/"},
                {"name": "loid",           "value": env["REDDIT_LOID"],       "domain": ".reddit.com", "path": "/"},
            ])
            page = ctx.new_page()
            page.goto(f"https://old.reddit.com/r/{subreddit}/submit", wait_until="domcontentloaded", timeout=30000)

            # Click the "text" tab to enable the body textarea
            page.evaluate("""
                const tabs = document.querySelectorAll('.tabmenu li a, #text-desc-link, a[href="#self"]');
                for (const t of tabs) {
                    if (t.textContent.trim().toLowerCase() === 'text' || t.id === 'text-desc-link') {
                        t.click(); break;
                    }
                }
            """)
            page.wait_for_timeout(800)

            page.fill("textarea[name=title]", args.title)
            # Wait for text area to be enabled after tab click
            page.wait_for_selector("textarea[name=text]:not([disabled])", timeout=5000)
            page.fill("textarea[name=text]", args.body)
            page.click("button[type=submit]")
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            url = page.url.replace("old.reddit.com", "reddit.com")
            m = _re.search(r"/comments/(\w+)/", url)
            browser.close()
    finally:
        if proxy_thread:
            proxy_thread.stop_fn()

    print(json.dumps({
        "id": m.group(1) if m else "",
        "url": url,
        "title": args.title,
        "subreddit": subreddit,
    }, indent=2))


def cmd_get_comments(args):
    data = api("GET", f"/comments/{args.post_id}?limit={args.limit}")
    comments = []
    for c in data[1]["data"]["children"]:
        if c["kind"] == "t1":
            d = c["data"]
            comments.append({
                "id": d["id"],
                "author": d["author"],
                "body": d["body"],
                "score": d["score"],
                "created_utc": d["created_utc"],
            })
    print(json.dumps(comments[:args.limit], indent=2))


def cmd_get_post(args):
    data = api("GET", f"/comments/{args.post_id}")
    d = data[0]["data"]["children"][0]["data"]
    print(json.dumps({
        "id": d["id"],
        "title": d["title"],
        "score": d["score"],
        "upvote_ratio": d["upvote_ratio"],
        "num_comments": d["num_comments"],
        "url": f"https://www.reddit.com{d['permalink']}",
        "created_utc": d["created_utc"],
    }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--subreddits")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--sort", default="relevance", choices=["relevance", "hot", "new", "top"])

    p_post = sub.add_parser("post")
    p_post.add_argument("--subreddit", required=True)
    p_post.add_argument("--title", required=True)
    p_post.add_argument("--body", required=True)

    p_comments = sub.add_parser("get-comments")
    p_comments.add_argument("--post-id", required=True)
    p_comments.add_argument("--limit", type=int, default=25)

    p_get = sub.add_parser("get-post")
    p_get.add_argument("--post-id", required=True)

    args = parser.parse_args()
    if args.command == "search":
        cmd_search(args)
    elif args.command == "post":
        cmd_post(args)
    elif args.command == "get-comments":
        cmd_get_comments(args)
    elif args.command == "get-post":
        cmd_get_post(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
