import os
import sqlite3
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "it_info.db")

SOURCES = [
    ("GitHub Blog", "https://github.blog/feed/"),
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("Ubuntu Security", "https://ubuntu.com/security/notices/rss.xml"),
]

app = Flask(__name__)


def db_connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db_connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                summary TEXT DEFAULT '',
                source TEXT NOT NULL,
                published_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )


def parse_date(entry):
    value = entry.get("published") or entry.get("updated")
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass
    return datetime.now(timezone.utc)


def refresh_articles():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    inserted = 0

    with db_connect() as db:
        for source_name, feed_url in SOURCES:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": "IT-Info-Hub/1.0"})
            for entry in feed.entries:
                url = entry.get("link", "").strip()
                title = entry.get("title", "Untitled").strip()
                published = parse_date(entry)
                if not url or published < cutoff:
                    continue
                summary = entry.get("summary", "")
                cursor = db.execute(
                    """
                    INSERT OR IGNORE INTO articles
                    (title, url, summary, source, published_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (title, url, summary, source_name, published.isoformat(), now.isoformat()),
                )
                inserted += cursor.rowcount

        db.execute("DELETE FROM articles WHERE published_at < ?", (cutoff.isoformat(),))
    return inserted


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/articles")
def articles():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    with db_connect() as db:
        rows = db.execute(
            """
            SELECT title, url, summary, source, published_at
            FROM articles
            WHERE published_at >= ?
            ORDER BY published_at DESC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/refresh")
def refresh():
    return jsonify({"ok": True, "inserted": refresh_articles()})


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler.add_job(refresh_articles, "cron", hour=9, minute=0, id="daily_refresh", replace_existing=True)
    scheduler.start()


if __name__ == "__main__":
    init_db()
    refresh_articles()
    start_scheduler()
    app.run(host="0.0.0.0", port=5001, debug=False)
