#!/usr/bin/env python3
"""
Run this on your LOCAL MACHINE (not the server) to refresh the Reddit token.
It opens a headless browser using your local IP, gets a fresh token_v2,
then POSTs it to the server to update .env.

Usage:
  python refresh_token_local.py --server ubuntu@<your-server-ip>

Requirements on your laptop:
  pip install playwright
  playwright install chromium
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile


def get_fresh_token(session, csrf, loid, current_token):
    from playwright.sync_api import sync_playwright

    cookie_hdr = f"reddit_session={session}; csrf_token={csrf}; loid={loid}; token_v2={current_token}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        ctx.route("**reddit.com**", lambda route: route.continue_(
            headers={**route.request.headers, "cookie": cookie_hdr}
        ))
        page = ctx.new_page()
        page.goto("https://www.reddit.com/", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        new_token = None
        for c in ctx.cookies():
            if c["name"] == "token_v2":
                new_token = c["value"]
                break

        browser.close()

    return new_token


def push_to_server(new_token, server):
    """SSH into the server and update REDDIT_TOKEN_V2 in .env"""
    script = f"""
python3 - <<'PYEOF'
env_path = '/home/ubuntu/slack-claude-bot/.env'
lines = open(env_path).readlines()
with open(env_path, 'w') as f:
    for line in lines:
        if line.startswith('REDDIT_TOKEN_V2='):
            f.write('REDDIT_TOKEN_V2={new_token}\\n')
        else:
            f.write(line)
print('Token updated on server.')
PYEOF
"""
    result = subprocess.run(["ssh", server, script], capture_output=True, text=True)
    if result.returncode != 0:
        print("SSH error:", result.stderr)
        sys.exit(1)
    print(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="ubuntu@YOUR_SERVER_IP",
                        help="SSH target, e.g. ubuntu@1.2.3.4")
    parser.add_argument("--env", default=None,
                        help="Path to .env file (if running locally without SSH)")
    args = parser.parse_args()

    # Read current values — either from local .env or via SSH
    if args.env:
        env = {}
        for line in open(args.env):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    else:
        result = subprocess.run(
            ["ssh", args.server, "cat /home/ubuntu/slack-claude-bot/.env"],
            capture_output=True, text=True
        )
        env = {}
        for line in result.stdout.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v

    session = env.get("REDDIT_SESSION", "")
    csrf = env.get("REDDIT_CSRF_TOKEN", "")
    loid = env.get("REDDIT_LOID", "")
    current_token = env.get("REDDIT_TOKEN_V2", "")

    if not session:
        print("ERROR: REDDIT_SESSION not found in .env")
        sys.exit(1)

    print("Getting fresh token from Reddit...")
    new_token = get_fresh_token(session, csrf, loid, current_token)

    if not new_token:
        print("ERROR: Could not get fresh token")
        sys.exit(1)

    changed = new_token != current_token
    print(f"Token {'changed' if changed else 'unchanged'}: {new_token[:40]}...")

    if args.env:
        # Update local .env directly
        lines = open(args.env).readlines()
        with open(args.env, "w") as f:
            for line in lines:
                if line.startswith("REDDIT_TOKEN_V2="):
                    f.write(f"REDDIT_TOKEN_V2={new_token}\n")
                else:
                    f.write(line)
        print("Updated local .env")
    else:
        push_to_server(new_token, args.server)


if __name__ == "__main__":
    main()
