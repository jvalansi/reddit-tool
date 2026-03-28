#!/usr/bin/env python3
"""Monitor Reddit posts and report scores + comments to Slack."""
import json
import os
import sys
import urllib.request

POSTS = [
    ("r/artificial",       "1s5sufx"),
    ("r/PromptEngineering","1s5sug0"),
    ("r/MachineLearning",  "1s5sukj"),
]

SLACK_TOKEN   = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("REDDIT_MONITOR_CHANNEL", "C0AMZ2XSW58")  # proj-project-validation
REDDIT_TOKEN  = os.environ.get("REDDIT_TOKEN_V2")
UA = "promptware-bot/1.0"


def reddit_api(path):
    url = f"https://oauth.reddit.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {REDDIT_TOKEN}",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def post_to_slack(text):
    if not SLACK_TOKEN:
        print(text)
        return
    body = json.dumps({"channel": SLACK_CHANNEL, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read())
        if not resp.get("ok"):
            print("Slack error:", resp.get("error"), file=sys.stderr)


def main():
    lines = ["*Promptware Reddit Monitor*"]
    for name, post_id in POSTS:
        try:
            data = reddit_api(f"/comments/{post_id}")
            post = data[0]["data"]["children"][0]["data"]
            score = post["score"]
            num_comments = post["num_comments"]

            top_comments = []
            for c in data[1]["data"]["children"]:
                if c["kind"] == "t1":
                    author = c["data"]["author"]
                    body = c["data"]["body"][:200].replace("\n", " ")
                    top_comments.append(f"  • u/{author}: {body}")
                    if len(top_comments) == 3:
                        break

            lines.append(f"\n*{name}* — score: {score}, comments: {num_comments} | https://reddit.com/r/{name.split('/')[1]}/comments/{post_id}")
            lines.extend(top_comments or ["  _(no comments yet)_"])
        except Exception as e:
            lines.append(f"\n*{name}* — error: {e}")

    post_to_slack("\n".join(lines))


if __name__ == "__main__":
    main()
