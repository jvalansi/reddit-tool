#!/usr/bin/env python3
"""
Reddit validation tool — search subreddits for pain points, post, and collect feedback.

Usage:
  python reddit_tool.py search --query QUERY [--subreddits r1,r2] [--limit N] [--sort hot|new|top]
  python reddit_tool.py post --subreddit NAME --title TITLE --body TEXT [--flair FLAIR]
  python reddit_tool.py get-comments --post-id ID [--limit N]
  python reddit_tool.py get-post --post-id ID
"""

import argparse
import json
import os
import sys

import praw


def get_reddit():
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")
    user_agent = os.environ.get("REDDIT_USER_AGENT", f"script:project-validator:v1.0 (by u/{username})")

    if not all([client_id, client_secret, username, password]):
        print(json.dumps({"error": "Missing Reddit credentials. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD in .env"}))
        sys.exit(1)

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=user_agent,
    )


def cmd_search(args):
    reddit = get_reddit()
    subreddits = args.subreddits.split(",") if args.subreddits else ["all"]
    results = []

    for sub in subreddits:
        sub = sub.strip().lstrip("r/")
        subreddit = reddit.subreddit(sub)
        for post in subreddit.search(args.query, sort=args.sort, limit=args.limit):
            results.append({
                "id": post.id,
                "subreddit": str(post.subreddit),
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "url": f"https://reddit.com{post.permalink}",
                "selftext": post.selftext[:500] if post.selftext else "",
                "created_utc": int(post.created_utc),
            })

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_post(args):
    reddit = get_reddit()
    subreddit = reddit.subreddit(args.subreddit.lstrip("r/"))

    submission = subreddit.submit(
        title=args.title,
        selftext=args.body,
        flair_id=args.flair if args.flair else None,
    )

    print(json.dumps({
        "id": submission.id,
        "url": f"https://reddit.com{submission.permalink}",
        "title": submission.title,
        "subreddit": str(submission.subreddit),
    }, indent=2))


def cmd_get_comments(args):
    reddit = get_reddit()
    submission = reddit.submission(id=args.post_id)
    submission.comments.replace_more(limit=0)

    comments = []
    for comment in submission.comments.list()[:args.limit]:
        comments.append({
            "id": comment.id,
            "author": str(comment.author) if comment.author else "[deleted]",
            "score": comment.score,
            "body": comment.body,
            "created_utc": int(comment.created_utc),
        })

    comments.sort(key=lambda c: c["score"], reverse=True)
    print(json.dumps(comments, indent=2, ensure_ascii=False))


def cmd_get_post(args):
    reddit = get_reddit()
    submission = reddit.submission(id=args.post_id)

    print(json.dumps({
        "id": submission.id,
        "title": submission.title,
        "score": submission.score,
        "upvote_ratio": submission.upvote_ratio,
        "num_comments": submission.num_comments,
        "url": f"https://reddit.com{submission.permalink}",
        "selftext": submission.selftext,
        "subreddit": str(submission.subreddit),
        "created_utc": int(submission.created_utc),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Reddit validation tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search subreddits for posts")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--subreddits", help="Comma-separated list of subreddits (default: all)")
    p_search.add_argument("--limit", type=int, default=10, help="Max results per subreddit (default: 10)")
    p_search.add_argument("--sort", default="relevance", choices=["relevance", "hot", "new", "top"], help="Sort order")

    # post
    p_post = subparsers.add_parser("post", help="Submit a post to a subreddit")
    p_post.add_argument("--subreddit", required=True, help="Subreddit name (with or without r/)")
    p_post.add_argument("--title", required=True, help="Post title")
    p_post.add_argument("--body", required=True, help="Post body text")
    p_post.add_argument("--flair", help="Flair ID (optional)")

    # get-comments
    p_comments = subparsers.add_parser("get-comments", help="Get comments on a post")
    p_comments.add_argument("--post-id", required=True, help="Reddit post ID")
    p_comments.add_argument("--limit", type=int, default=50, help="Max comments to fetch (default: 50)")

    # get-post
    p_getpost = subparsers.add_parser("get-post", help="Get post metadata")
    p_getpost.add_argument("--post-id", required=True, help="Reddit post ID")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "post":
        cmd_post(args)
    elif args.command == "get-comments":
        cmd_get_comments(args)
    elif args.command == "get-post":
        cmd_get_post(args)


if __name__ == "__main__":
    main()
