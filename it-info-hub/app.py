import os
import re
import sqlite3
import threading
import time
import calendar
import html
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "it_info.db")

SOURCES = [
    ("GitHub Blog", "https://github.blog/feed/"),
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("Ubuntu Security", "https://ubuntu.com/security/notices/rss.xml"),
    ("Google Security", "https://security.googleblog.com/feeds/posts/default"),
    ("Microsoft Security", "https://www.microsoft.com/en-us/security/blog/feed/"),
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss/"),
    ("Docker Blog", "https://www.docker.com/blog/feed/"),
    ("Kubernetes Blog", "https://kubernetes.io/feed.xml"),
    ("Python Blog", "https://blog.python.org/feeds/posts/default"),
    ("Mozilla Hacks", "https://hacks.mozilla.org/feed/"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
]

app = Flask(__name__)
refresh_lock = threading.Lock()
last_manual_refresh = 0.0


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
        columns = {row[1] for row in db.execute("PRAGMA table_info(articles)")}
        if "image_url" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN image_url TEXT DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        db.execute("""CREATE TABLE IF NOT EXISTS source_status (
            source TEXT PRIMARY KEY, ok INTEGER NOT NULL, message TEXT DEFAULT '', fetched_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS github_trending (
            snapshot_date TEXT NOT NULL, rank INTEGER NOT NULL, repo_name TEXT NOT NULL,
            url TEXT NOT NULL, description TEXT DEFAULT '', language TEXT DEFAULT '', stars TEXT DEFAULT '',
            PRIMARY KEY (snapshot_date, repo_name))""")


def parse_date(entry):
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        try:
            return datetime.fromtimestamp(calendar.timegm(parsed_struct), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass
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


def image_from_entry(entry):
    for field in ("media_content", "media_thumbnail"):
        for media in entry.get(field, []):
            url = str(media.get("url", "")).strip()
            if url.startswith(("https://", "http://")):
                return url
    for item in entry.get("enclosures", []):
        url = str(item.get("href", "")).strip()
        if str(item.get("type", "")).startswith("image/") and url.startswith(("https://", "http://")):
            return url
    match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)', entry.get("summary", ""), re.I)
    return match.group(1) if match else ""


def clean_html(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def refresh_github_trending(now):
    request_obj = urllib.request.Request(
        "https://github.com/trending?since=daily",
        headers={"User-Agent": "IT-Info-Hub/2.0", "Accept-Language": "en-US,en;q=0.8"},
    )
    with urllib.request.urlopen(request_obj, timeout=20) as response:
        page = response.read().decode("utf-8", errors="replace")
    blocks = re.findall(r'<article[^>]+class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>', page, re.S | re.I)
    snapshot_date = now.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    records = []
    for rank, block in enumerate(blocks[:25], 1):
        repo_match = re.search(r'<h2.*?<a[^>]+href="/([^"?#]+)"', block, re.S | re.I)
        if not repo_match:
            continue
        repo_name = repo_match.group(1).strip()
        description = re.search(r'<p[^>]*>(.*?)</p>', block, re.S | re.I)
        language = re.search(r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', block, re.S | re.I)
        stars = re.search(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', block, re.S | re.I)
        records.append((snapshot_date, rank, repo_name, f"https://github.com/{repo_name}",
                        clean_html(description.group(1)) if description else "",
                        clean_html(language.group(1)) if language else "",
                        clean_html(stars.group(1)) if stars else ""))
    with db_connect() as db:
        db.executemany("""INSERT OR REPLACE INTO github_trending
            (snapshot_date, rank, repo_name, url, description, language, stars)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", records)
    return len(records)


def refresh_articles():
    now = datetime.now(timezone.utc)
    inserted = 0
    source_results = []

    with db_connect() as db:
        for source_name, feed_url in SOURCES:
            try:
                feed = feedparser.parse(feed_url, request_headers={"User-Agent": "IT-Info-Hub/2.0"})
                if getattr(feed, "bozo", False) and not feed.entries:
                    raise RuntimeError(str(getattr(feed, "bozo_exception", "RSS 讀取失敗")))
                count = 0
                for entry in feed.entries[:80]:
                    url = entry.get("link", "").strip()
                    if not url:
                        continue
                    cursor = db.execute("""INSERT OR IGNORE INTO articles
                        (title, url, summary, source, published_at, fetched_at, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (entry.get("title", "Untitled").strip(), url, entry.get("summary", ""), source_name,
                         parse_date(entry).isoformat(), now.isoformat(), image_from_entry(entry)))
                    count += cursor.rowcount
                inserted += count
                source_results.append({"source": source_name, "ok": True, "inserted": count})
                db.execute("INSERT OR REPLACE INTO source_status VALUES (?, 1, ?, ?)",
                           (source_name, f"新增 {count} 篇", now.isoformat()))
            except Exception as exc:
                message = str(exc)[:160]
                source_results.append({"source": source_name, "ok": False, "message": message})
                db.execute("INSERT OR REPLACE INTO source_status VALUES (?, 0, ?, ?)",
                           (source_name, message, now.isoformat()))
        db.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('last_refresh', ?)",
            (now.isoformat(),),
        )
    try:
        ranking_count = refresh_github_trending(now)
    except Exception as exc:
        ranking_count = 0
        source_results.append({"source": "GitHub Trending", "ok": False, "message": str(exc)[:160]})
    return {"inserted": inserted, "sources": source_results, "ranking_count": ranking_count}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/articles")
def articles():
    selected_date = request.args.get("date", "").strip()
    with db_connect() as db:
        if selected_date:
            rows = db.execute("""SELECT id, title, url, summary, source, published_at, image_url
                FROM articles WHERE date(published_at, '+8 hours') = ?
                ORDER BY published_at DESC LIMIT 1000""", (selected_date,)).fetchall()
        else:
            rows = db.execute("""SELECT id, title, url, summary, source, published_at, image_url
                FROM articles ORDER BY published_at DESC LIMIT 500""").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/archive")
def archive():
    with db_connect() as db:
        rows = db.execute("""SELECT date(published_at, '+8 hours') AS date, COUNT(*) AS count
            FROM articles GROUP BY date(published_at, '+8 hours') ORDER BY date DESC""").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/trending")
def trending():
    selected_date = request.args.get("date", "").strip()
    with db_connect() as db:
        if not selected_date:
            row = db.execute("SELECT MAX(snapshot_date) AS date FROM github_trending").fetchone()
            selected_date = row["date"] if row else ""
        rows = db.execute("""SELECT rank, repo_name, url, description, language, stars
            FROM github_trending WHERE snapshot_date = ? ORDER BY rank""", (selected_date,)).fetchall()
    return jsonify({"date": selected_date, "items": [dict(row) for row in rows]})


@app.post("/api/refresh")
def refresh():
    global last_manual_refresh
    if not request.is_json and request.content_length:
        return jsonify({"ok": False, "error": "不支援的內容格式"}), 415
    now = time.monotonic()
    if now - last_manual_refresh < 60:
        return jsonify({"ok": False, "error": "更新過於頻繁，請稍後再試"}), 429
    if not refresh_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "正在更新中"}), 409
    try:
        last_manual_refresh = now
        result = refresh_articles()
        return jsonify({"ok": True, **result})
    finally:
        refresh_lock.release()


@app.route("/api/status")
def status():
    with db_connect() as db:
        row = db.execute("SELECT value FROM app_meta WHERE key = 'last_refresh'").fetchone()
        sources = db.execute("SELECT source, ok, message, fetched_at FROM source_status ORDER BY source").fetchall()
        total = db.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
    return jsonify({"last_refresh": row["value"] if row else None, "total_articles": total,
                    "sources": [dict(item) for item in sources]})


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler.add_job(refresh_articles, "cron", hour=9, minute=0, id="daily_refresh", replace_existing=True)
    scheduler.start()


if __name__ == "__main__":
    init_db()
    refresh_articles()
    start_scheduler()
    app.run(host="0.0.0.0", port=5001, debug=False)
