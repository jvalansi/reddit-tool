#!/usr/bin/env python3
"""
Reddit validation tool — delegates to reddit_playwright.py (token_v2 approach).

Usage:
  python reddit_tool.py search --query QUERY [--subreddits r1,r2] [--limit N] [--sort relevance|hot|new|top]
  python reddit_tool.py post --subreddit NAME --title TITLE --body TEXT
  python reddit_tool.py get-comments --post-id ID [--limit N]
  python reddit_tool.py get-post --post-id ID
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from reddit_playwright import main

if __name__ == "__main__":
    main()
