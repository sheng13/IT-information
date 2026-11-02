import os
import re
import sqlite3
import threading
import time
import calendar
import html
import json
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request

try:
    from scrapling import Fetcher
except Exception:
    Fetcher = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "it_info.db"))

# RSS/Atom news feeds, including vendor, security, cloud, AI, and hardware news.
NEWS_SOURCES = [
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
    ("LWN.net", "https://lwn.net/headlines/rss"),
    ("InfoQ", "https://www.infoq.com/feed?output=1"),
    ("Fedora Magazine", "https://fedoramagazine.org/feed/"),
    ("Red Hat Blog", "https://www.redhat.com/en/rss/blog"),
    ("CISA Advisories", "https://www.cisa.gov/news-events/cybersecurity-advisories?format=rss"),
    ("CNCF Blog", "https://www.cncf.io/blog/feed/"),
    ("Open Source", "https://opensource.com/feed"),
    ("The New Stack", "https://thenewstack.io/feed/"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/"),
    ("Cisco Blog", "https://blogs.cisco.com/rss"),
    ("Dell Tech Blog", "https://www.dell.com/en-us/blog/feed/"),
    ("Lenovo News", "https://news.lenovo.com/feed/"),
    ("Lenovo Press", "https://lenovopress.lenovo.com/rss"),
    ("Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss"),
    ("Apple Machine Learning", "https://machinelearning.apple.com/rss.xml"),
    ("Samsung Newsroom", "https://news.samsung.com/global/feed"),
    ("Samsung Semiconductor", "https://news.samsung.com/global/category/semiconductor/feed"),
    # Xiaomi currently returns an HTML page here; replace with its current RSS URL when available.
    ("Xiaomi Blog", "https://blog.mi.com/en/feed/"),
    ("Mozilla Security", "https://blog.mozilla.org/security/feed/"),
    ("Google DeepMind AI", "https://blog.google/technology/ai/rss/"),
    ("AI News", "https://www.artificialintelligence-news.com/feed/"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Python CPython Releases", "https://github.com/python/cpython/releases.atom"),
    ("Kubernetes Releases", "https://github.com/kubernetes/kubernetes/releases.atom"),
    ("Docker Compose Releases", "https://github.com/docker/compose/releases.atom"),
    ("Node.js Releases", "https://github.com/nodejs/node/releases.atom"),
    ("Rails Releases", "https://github.com/rails/rails/releases.atom"),
    ("TensorFlow Releases", "https://github.com/tensorflow/tensorflow/releases.atom"),
]

# GitHub release feeds provide version updates for widely used software projects.
RELEASE_SOURCES = [
    ("Go Releases", "https://github.com/golang/go/releases.atom"),
    ("Rust Releases", "https://github.com/rust-lang/rust/releases.atom"),
    ("React Releases", "https://github.com/facebook/react/releases.atom"),
    ("Vue Releases", "https://github.com/vuejs/core/releases.atom"),
    ("Django Releases", "https://github.com/django/django/releases.atom"),
    ("Flask Releases", "https://github.com/pallets/flask/releases.atom"),
    ("FastAPI Releases", "https://github.com/fastapi/fastapi/releases.atom"),
    ("PostgreSQL Releases", "https://github.com/postgres/postgres/releases.atom"),
    ("Redis Releases", "https://github.com/redis/redis/releases.atom"),
    ("Nginx Releases", "https://github.com/nginx/nginx/releases.atom"),
    ("OpenSSL Releases", "https://github.com/openssl/openssl/releases.atom"),
    ("Terraform Releases", "https://github.com/hashicorp/terraform/releases.atom"),
    ("Ansible Releases", "https://github.com/ansible/ansible/releases.atom"),
    ("Helm Releases", "https://github.com/helm/helm/releases.atom"),
    ("Prometheus Releases", "https://github.com/prometheus/prometheus/releases.atom"),
    ("Grafana Releases", "https://github.com/grafana/grafana/releases.atom"),
    ("Argo CD Releases", "https://github.com/argoproj/argo-cd/releases.atom"),
    ("Istio Releases", "https://github.com/istio/istio/releases.atom"),
    ("Envoy Releases", "https://github.com/envoyproxy/envoy/releases.atom"),
    ("MinIO Releases", "https://github.com/minio/minio/releases.atom"),
    ("Elasticsearch Releases", "https://github.com/elastic/elasticsearch/releases.atom"),
    ("Spring Boot Releases", "https://github.com/spring-projects/spring-boot/releases.atom"),
    (".NET Releases", "https://github.com/dotnet/runtime/releases.atom"),
    ("PHP Releases", "https://github.com/php/php-src/releases.atom"),
    ("Laravel Releases", "https://github.com/laravel/framework/releases.atom"),
    ("Ruby Releases", "https://github.com/ruby/ruby/releases.atom"),
    ("Home Assistant Releases", "https://github.com/home-assistant/core/releases.atom"),
    ("Ollama Releases", "https://github.com/ollama/ollama/releases.atom"),
    ("PyTorch Releases", "https://github.com/pytorch/pytorch/releases.atom"),
    ("Jupyter Releases", "https://github.com/jupyter/notebook/releases.atom"),
    ("VS Code Releases", "https://github.com/microsoft/vscode/releases.atom"),
    ("Neovim Releases", "https://github.com/neovim/neovim/releases.atom"),
    # AI Agent frameworks, protocols, model tooling, and autonomous coding tools.
    ("LangChain Releases", "https://github.com/langchain-ai/langchain/releases.atom"),
    ("LlamaIndex Releases", "https://github.com/run-llama/llama_index/releases.atom"),
    ("AutoGen Releases", "https://github.com/microsoft/autogen/releases.atom"),
    ("CrewAI Releases", "https://github.com/crewAIInc/crewAI/releases.atom"),
    ("Semantic Kernel Releases", "https://github.com/microsoft/semantic-kernel/releases.atom"),
    ("Haystack Releases", "https://github.com/deepset-ai/haystack/releases.atom"),
    ("Pydantic AI Releases", "https://github.com/pydantic/pydantic-ai/releases.atom"),
    ("MCP Python Releases", "https://github.com/modelcontextprotocol/python-sdk/releases.atom"),
    ("MCP TypeScript Releases", "https://github.com/modelcontextprotocol/typescript-sdk/releases.atom"),
    ("MCP Servers Releases", "https://github.com/modelcontextprotocol/servers/releases.atom"),
    ("OpenHands Releases", "https://github.com/All-Hands-AI/OpenHands/releases.atom"),
    ("Aider Releases", "https://github.com/Aider-AI/aider/releases.atom"),
    ("Continue Releases", "https://github.com/continuedev/continue/releases.atom"),
    ("Cline Releases", "https://github.com/cline/cline/releases.atom"),
    ("Browser Use Releases", "https://github.com/browser-use/browser-use/releases.atom"),
    ("Dify Releases", "https://github.com/langgenius/dify/releases.atom"),
    ("Flowise Releases", "https://github.com/FlowiseAI/Flowise/releases.atom"),
    ("LiteLLM Releases", "https://github.com/BerriAI/litellm/releases.atom"),
    ("vLLM Releases", "https://github.com/vllm-project/vllm/releases.atom"),
    ("Transformers Releases", "https://github.com/huggingface/transformers/releases.atom"),
    ("Smolagents Releases", "https://github.com/huggingface/smolagents/releases.atom"),
]

SOURCES = NEWS_SOURCES + RELEASE_SOURCES

SOURCE_CATEGORIES = {
    "GitHub Blog": "Software",
    "Hacker News": "Software",
    "Ubuntu Security": "Security",
    "Google Security": "Security",
    "Microsoft Security": "Security",
    "Cloudflare Blog": "Cloud",
    "Docker Blog": "Software",
    "Kubernetes Blog": "Software",
    "Python Blog": "Software",
    "Mozilla Hacks": "Software",
    "The Hacker News": "Security",
    "BleepingComputer": "Security",
    "LWN.net": "Software",
    "InfoQ": "Software",
    "Fedora Magazine": "Software",
    "Red Hat Blog": "Software",
    "CISA Advisories": "Security",
    "CNCF Blog": "Cloud",
    "Open Source": "Software",
    "The New Stack": "Cloud",
    "NVIDIA Blog": "Hardware",
    "Cisco Blog": "Hardware",
    "Dell Tech Blog": "Hardware",
    "Lenovo News": "Hardware",
    "Lenovo Press": "Hardware",
    "Apple Newsroom": "Hardware",
    "Apple Machine Learning": "AI",
    "Samsung Newsroom": "Hardware",
    "Samsung Semiconductor": "Hardware",
    "Xiaomi Blog": "Hardware",
    "Mozilla Security": "Security",
    "Google DeepMind AI": "AI",
    "AI News": "AI",
    "MIT Technology Review AI": "AI",
    "The Verge AI": "AI",
    "Python CPython Releases": "Software Release",
    "Kubernetes Releases": "Software Release",
    "Docker Compose Releases": "Software Release",
    "Node.js Releases": "Software Release",
    "Rails Releases": "Software Release",
    "TensorFlow Releases": "AI Release",
}
# New release sources inherit a category automatically; special AI projects override it below.
SOURCE_CATEGORIES.update({source: "Software Release" for source, _ in RELEASE_SOURCES})
SOURCE_CATEGORIES.update({
    "Ollama Releases": "AI Release",
    "PyTorch Releases": "AI Release",
})
SOURCE_CATEGORIES.update({
    source: "AI Agent"
    for source, _ in RELEASE_SOURCES
    if any(keyword in source for keyword in (
        "LangChain", "LlamaIndex", "AutoGen", "CrewAI", "Semantic Kernel", "Haystack",
        "Pydantic AI", "MCP", "OpenHands", "Aider", "Continue", "Cline", "Browser Use",
        "Dify", "Flowise", "LiteLLM", "vLLM", "Transformers", "Smolagents",
    ))
})

scrapling_fetcher = Fetcher() if Fetcher else None

app = Flask(__name__)
refresh_lock = threading.Lock()
last_manual_refresh = 0.0
PORT = int(os.environ.get("PORT", "5001"))


@app.errorhandler(404)
def handle_not_found(error):
    # API 路由不存在時也回傳 JSON，避免前端把 HTML 錯誤頁當成 JSON 解析。
    if request.path.startswith("/api/"):
        return jsonify({"error": "API 路由不存在", "path": request.path}), 404
    return error


@app.errorhandler(500)
def handle_server_error(error):
    # API 發生未預期例外時保持固定 JSON 格式，方便前端顯示可讀錯誤。
    if request.path.startswith("/api/"):
        return jsonify({"error": "伺服器發生錯誤"}), 500
    return error


def db_connect():
    # 建立 SQLite 連線，並讓查詢結果可以用欄位名稱存取。
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    # 建立目前版本需要的資料表，並為舊資料補上新欄位。
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
                fetched_at TEXT NOT NULL,
                category TEXT DEFAULT ''
            )
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(articles)")}
        if "image_url" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN image_url TEXT DEFAULT ''")
        if "category" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN category TEXT DEFAULT ''")
        db.executemany(
            "UPDATE articles SET category = ? WHERE source = ? AND (category IS NULL OR category = '')",
            [(category, source) for source, category in SOURCE_CATEGORIES.items()],
        )
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
        columns = {row[1] for row in db.execute("PRAGMA table_info(source_status)")}
        if "last_success_at" not in columns:
            db.execute("ALTER TABLE source_status ADD COLUMN last_success_at TEXT")
            db.execute("UPDATE source_status SET last_success_at = fetched_at WHERE ok = 1")
        db.execute("""CREATE TABLE IF NOT EXISTS github_trending (
            snapshot_date TEXT NOT NULL, rank INTEGER NOT NULL, repo_name TEXT NOT NULL,
            url TEXT NOT NULL, description TEXT DEFAULT '', language TEXT DEFAULT '', stars TEXT DEFAULT '',
            PRIMARY KEY (snapshot_date, repo_name))""")


def parse_date(entry):
    # 優先解析 RSS 的結構化日期，失敗時再解析文字日期。
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
    # 依序從 RSS 媒體欄位、附件和摘要 HTML 找文章圖片。
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
    # 將 RSS 摘要中的 HTML 標籤移除，避免純文字顯示出標記。
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def translate_text(value, target="zh-TW"):
    # 呼叫外部翻譯服務，target 預設為繁體中文。
    if not value.strip():
        return ""
    # Keep translation server-side so the browser does not need a translation API key.
    query = urllib.parse.urlencode({"q": value, "langpair": f"autodetect|{target}"})
    request_obj = urllib.request.Request(
        f"https://api.mymemory.translated.net/get?{query}",
        headers={"User-Agent": "IT-Info-Hub/2.0"},
    )
    with urllib.request.urlopen(request_obj, timeout=15) as response:
        translated = json.loads(response.read().decode("utf-8"))
    if translated.get("responseStatus") != 200:
        raise RuntimeError(translated.get("responseDetails", "translation service error"))
    return translated["responseData"]["translatedText"]


def enrich_from_scrapling(url, summary='', image_url=''):
    # RSS 缺少摘要或圖片時，從文章頁面的 meta 標籤補充資料。
    if not scrapling_fetcher or not url:
        return summary, image_url
    try:
        response = scrapling_fetcher.get(url, timeout=15)
        if getattr(response, 'status', 200) != 200:
            return summary, image_url
        page = str(response.html_content or response.body or '')
        if not image_url:
            image_match = re.search(r'<meta[^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])[^>]+content=["\']([^"\']+)["\']', page, re.I | re.S)
            if image_match:
                image_url = image_match.group(1).strip()
        if not summary.strip():
            summary_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', page, re.I | re.S)
            if summary_match:
                summary = summary_match.group(1).strip()
        return clean_html(summary), image_url
    except Exception:
        return summary, image_url


def refresh_github_trending(now):
    # 抓取 GitHub 每日熱門專案，並保存當天的排行快照。
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
    if not records:
        raise ValueError("GitHub Trending 格式異常，未取得排行")
    with db_connect() as db:
        db.execute("DELETE FROM github_trending WHERE snapshot_date = ?", (snapshot_date,))
        db.executemany("""INSERT OR REPLACE INTO github_trending
            (snapshot_date, rank, repo_name, url, description, language, stars)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", records)
    return len(records)


def retry_fetch(operation):
    # 暫時性網路錯誤最多嘗試三次；網址或格式錯誤直接回報。
    for attempt in range(3):
        try:
            return operation()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": "IT-Info-Hub/2.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        feed = feedparser.parse(response.read())
    if not feed.get("version") or (feed.get("bozo") and not feed.entries):
        raise ValueError("RSS 格式異常：" + str(feed.get("bozo_exception", "不是有效 RSS/Atom"))[:120])
    return feed


def save_source_status(source, ok, message):
    timestamp = datetime.now(timezone.utc).isoformat()
    with db_connect() as db:
        db.execute("""INSERT INTO source_status (source, ok, message, fetched_at, last_success_at)
            VALUES (?, ?, ?, ?, ?) ON CONFLICT(source) DO UPDATE SET
            ok = excluded.ok, message = excluded.message, fetched_at = excluded.fetched_at,
            last_success_at = CASE WHEN excluded.ok = 1 THEN excluded.last_success_at
                                   ELSE source_status.last_success_at END""",
            (source, int(ok), message, timestamp, timestamp if ok else None))


def refresh_articles(failed_only=False):
    # ponytail: 單一程序共用鎖；部署多程序時改用資料庫協調。
    if not refresh_lock.acquire(blocking=False):
        raise RuntimeError("正在更新中")
    try:
        return refresh_selected_sources(failed_only)
    finally:
        refresh_lock.release()


def refresh_selected_sources(failed_only):
    now = datetime.now(timezone.utc)
    inserted = 0
    source_results = []
    ranking_count = 0
    with db_connect() as db:
        failed = {row["source"] for row in db.execute("SELECT source FROM source_status WHERE ok = 0")}
    for source_name, feed_url in SOURCES:
        if failed_only and source_name not in failed:
            continue
        try:
            feed = retry_fetch(lambda: fetch_feed(feed_url))
            records = []
            with db_connect() as db:
                existing = {row["url"] for row in db.execute("SELECT url FROM articles WHERE source = ?", (source_name,))}
            for entry in feed.entries[:80]:
                url = entry.get("link", "").strip()
                if not url or url in existing:
                    continue
                summary = entry.get("summary", "") or ""
                image_url = image_from_entry(entry)
                if not summary.strip() or not image_url:
                    summary, image_url = enrich_from_scrapling(url, summary, image_url)
                records.append((entry.get("title", "Untitled").strip(), url, summary, source_name,
                    parse_date(entry).isoformat(), now.isoformat(), image_url,
                    SOURCE_CATEGORIES.get(source_name, "Other")))
            with db_connect() as db:
                before = db.total_changes
                db.executemany("""INSERT OR IGNORE INTO articles
                    (title, url, summary, source, published_at, fetched_at, image_url, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", records)
                count = db.total_changes - before
            inserted += count
            save_source_status(source_name, True, f"新增 {count} 篇")
            source_results.append({"source": source_name, "ok": True, "inserted": count})
        except Exception as exc:
            message = str(exc)[:160] or type(exc).__name__
            save_source_status(source_name, False, message)
            source_results.append({"source": source_name, "ok": False, "message": message})
    if not failed_only or "GitHub Trending" in failed:
        try:
            ranking_count = retry_fetch(lambda: refresh_github_trending(now))
            save_source_status("GitHub Trending", True, f"取得 {ranking_count} 筆排行")
            source_results.append({"source": "GitHub Trending", "ok": True})
        except Exception as exc:
            message = str(exc)[:160] or type(exc).__name__
            save_source_status("GitHub Trending", False, message)
            source_results.append({"source": "GitHub Trending", "ok": False, "message": message})
    succeeded = sum(item["ok"] for item in source_results)
    with db_connect() as db:
        if source_results:
            db.execute("INSERT OR REPLACE INTO app_meta VALUES ('last_attempt', ?)", (now.isoformat(),))
            db.execute("INSERT OR REPLACE INTO app_meta VALUES ('refresh_outcome', ?)",
                       ("failed" if not succeeded else "partial" if succeeded < len(source_results) else "success",))
        if succeeded:
            db.execute("INSERT OR REPLACE INTO app_meta VALUES ('last_refresh', ?)", (now.isoformat(),))
    return {"ok": bool(succeeded) or not source_results, "inserted": inserted,
            "sources": source_results, "ranking_count": ranking_count,
            "failed_count": len(source_results) - succeeded}


@app.route("/")
def index():
    # 回傳前端單頁應用程式。
    return render_template("index.html")


@app.route("/api/articles")
def articles():
    # 依日期取得文章；未指定日期時回傳最新文章。
    selected_date = request.args.get("date", "").strip()
    with db_connect() as db:
        if selected_date:
            rows = db.execute("""SELECT id, title, url, summary, source, published_at, image_url, category
                FROM articles WHERE date(published_at, '+8 hours') = ?
                ORDER BY published_at DESC LIMIT 1000""", (selected_date,)).fetchall()
        else:
            rows = db.execute("""SELECT id, title, url, summary, source, published_at, image_url, category
                FROM articles ORDER BY published_at DESC LIMIT 500""").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/archive")
def archive():
    # 回傳每日文章數量，供前端建立年份、月份和日期篩選器。
    with db_connect() as db:
        rows = db.execute("""SELECT date(published_at, '+8 hours') AS date, COUNT(*) AS count
            FROM articles GROUP BY date(published_at, '+8 hours') ORDER BY date DESC""").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/trending")
def trending():
    # 取得指定日期或最新日期的 GitHub Trending 排行。
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
    # 手動觸發更新，並用鎖和冷卻時間避免重複大量抓取。
    global last_manual_refresh
    if not request.is_json and request.content_length:
        return jsonify({"ok": False, "error": "不支援的內容格式"}), 415
    payload = request.get_json(silent=True) if request.is_json else {}
    if not isinstance(payload, dict) or not isinstance(payload.get("failed_only", False), bool):
        return jsonify({"ok": False, "error": "更新參數格式錯誤"}), 400
    now = time.monotonic()
    if refresh_lock.locked():
        return jsonify({"ok": False, "error": "正在更新中"}), 409
    if now - last_manual_refresh < 60:
        return jsonify({"ok": False, "error": "更新過於頻繁，請稍後再試"}), 429
    last_manual_refresh = now
    try:
        return jsonify(refresh_articles(failed_only=payload.get("failed_only", False)))
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@app.route("/api/status")
def status():
    # 回傳最後更新時間、文章總數和各來源健康狀態。
    with db_connect() as db:
        row = db.execute("SELECT value FROM app_meta WHERE key = 'last_refresh'").fetchone()
        sources = db.execute("SELECT source, ok, message, fetched_at, last_success_at FROM source_status ORDER BY source").fetchall()
        meta = dict(db.execute("SELECT key, value FROM app_meta"))
        total = db.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
    return jsonify({"last_refresh": row["value"] if row else None, "total_articles": total, "last_attempt": meta.get("last_attempt"),
                    "refresh_outcome": meta.get("refresh_outcome"), "refreshing": refresh_lock.locked(),
                    "sources": [dict(item) for item in sources]})


@app.route("/api/sources")
def sources():
    # 固定回傳完整來源目錄，讓尚未抓到文章的新來源也能被看見。
    with db_connect() as db:
        counts = {
            row["source"]: row["count"]
            for row in db.execute("SELECT source, COUNT(*) AS count FROM articles GROUP BY source")
        }
        health = {
            row["source"]: dict(row)
            for row in db.execute("SELECT source, ok, message, fetched_at, last_success_at FROM source_status")
        }
    return jsonify([
        {
            "source": source,
            "category": SOURCE_CATEGORIES.get(source, "Other"),
            "count": counts.get(source, 0),
            "ok": health.get(source, {}).get("ok"),
            "message": health.get(source, {}).get("message", "尚未抓取"),
            "fetched_at": health.get(source, {}).get("fetched_at"),
            "last_success_at": health.get(source, {}).get("last_success_at"),
        }
        for source, _ in SOURCES
    ])


@app.post("/api/translate")
def translate():
    # 翻譯前端傳來的標題和摘要，並限制輸入長度避免濫用外部服務。
    payload = request.get_json(silent=True) or {}
    title = clean_html(str(payload.get("title", ""))).strip()
    summary = clean_html(str(payload.get("summary", ""))).strip()
    if not title and not summary:
        return jsonify({"error": "沒有可翻譯的內容"}), 400
    if len(title) + len(summary) > 4000:
        return jsonify({"error": "翻譯內容過長"}), 413
    try:
        translated = translate_text(f"{title}\n\n{summary}".strip())
        translated_title, _, translated_summary = translated.partition("\n\n")
        return jsonify({"title": translated_title, "summary": translated_summary})
    except Exception as exc:
        app.logger.warning("Translation failed: %s", exc)
        return jsonify({"error": "翻譯服務暫時無法使用"}), 502


def start_scheduler():
    # 每天台灣時間 09:00 自動執行一次資料更新。
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler.add_job(refresh_articles, "cron", hour=9, minute=0, id="daily_refresh", replace_existing=True)
    scheduler.start()


def refresh_in_background():
    # 啟動時在背景更新資料，避免抓取來源阻塞網站啟動。
    try:
        refresh_articles()
    except Exception as exc:
        app.logger.exception("Initial refresh failed: %s", exc)


if __name__ == "__main__":
    init_db()
    start_scheduler()
    # Let health checks reach Flask before the first network-heavy refresh begins.
    threading.Timer(10, refresh_in_background).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
