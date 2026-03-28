#!/usr/bin/env python3
"""
Refresh REDDIT_TOKEN_V2 in slack-claude-bot/.env by loading reddit.com
in a headless browser with the current cookies — Reddit's JS issues a fresh token.

Run every 12h via cron or systemd timer.
"""

import base64, os, select, socket, sys, threading, time

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "slack-claude-bot", ".env")

def load_env():
    env = {}
    for line in open(ENV_PATH):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def save_token(new_token):
    lines = open(ENV_PATH).readlines()
    with open(ENV_PATH, "w") as f:
        for line in lines:
            if line.startswith("REDDIT_TOKEN_V2="):
                f.write(f"REDDIT_TOKEN_V2={new_token}\n")
            else:
                f.write(line)


def start_proxy(proxy_url, port=18899):
    url = proxy_url.replace("http://", "").rstrip("/")
    auth, hostport = url.rsplit("@", 1)
    host, p = hostport.rsplit(":", 1)
    auth_b64 = base64.b64encode(auth.encode()).decode()

    def pipe(a, b):
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 30)
                if not r: break
                for s in r:
                    d = s.recv(4096)
                    if not d: return
                    (b if s is a else a).sendall(d)
        except: pass
        finally:
            for s in [a, b]:
                try: s.close()
                except: pass

    def handle(client):
        try:
            req = b""
            while b"\r\n\r\n" not in req: req += client.recv(4096)
            _, target, _ = req.split(b"\r\n")[0].decode().split(" ", 2)
            up = socket.create_connection((host, int(p)), timeout=30)
            up.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Authorization: Basic {auth_b64}\r\n\r\n".encode())
            resp = b""
            while b"\r\n\r\n" not in resp: resp += up.recv(4096)
            if b"200" in resp.split(b"\r\n")[0]:
                client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                pipe(client, up)
            else:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except: pass
        finally:
            try: client.close()
            except: pass

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(50)
    srv.settimeout(1)

    def run():
        while not getattr(run, "stop", False):
            try:
                c, _ = srv.accept()
                threading.Thread(target=handle, args=(c,), daemon=True).start()
            except socket.timeout: continue
            except: break
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.stop_fn = lambda: setattr(run, "stop", True)
    return t


def refresh():
    from playwright.sync_api import sync_playwright

    env = load_env()
    proxy_url = env.get("REDDIT_PROXY_URL", "")
    old_token = env.get("REDDIT_TOKEN_V2", "")

    proxy_thread = start_proxy(proxy_url) if proxy_url else None
    if proxy_thread:
        time.sleep(0.5)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                proxy={"server": "http://127.0.0.1:18899"} if proxy_url else None,
                args=["--no-sandbox"],
            )
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            ctx.add_cookies([
                {"name": "csrf_token", "value": env["REDDIT_CSRF_TOKEN"], "domain": ".reddit.com", "path": "/"},
                {"name": "loid",       "value": env["REDDIT_LOID"],       "domain": ".reddit.com", "path": "/"},
                {"name": "token_v2",   "value": old_token,                "domain": ".reddit.com", "path": "/"},
            ])
            page = ctx.new_page()
            page.goto("https://www.reddit.com/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            new_token = None
            for c in ctx.cookies():
                if c["name"] == "token_v2":
                    new_token = c["value"]
                    break

            browser.close()
    finally:
        if proxy_thread:
            proxy_thread.stop_fn()

    if not new_token:
        print("ERROR: could not retrieve fresh token", file=sys.stderr)
        sys.exit(1)

    save_token(new_token)
    changed = new_token != old_token
    print(f"Token {'refreshed' if changed else 'unchanged'}: {new_token[:40]}...")
    return new_token


if __name__ == "__main__":
    refresh()
