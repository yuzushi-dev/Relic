"""Cron entrypoint: relic:reply-extract

Invoked as: python -m relic.reply_extract
Schedule:   0 */6 * * *

Processes pending check-in replies: runs LLM extraction on captured replies
and writes observations back to the database.
"""
from relic.relic_reply_extractor import main

if __name__ == "__main__":
    main()
