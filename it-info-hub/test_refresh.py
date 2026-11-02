import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
import app

RSS = b'<rss version="2.0"><channel><title>News</title><link>https://example.com</link><description>News</description><item><title>Saved</title><link>https://example.com/article</link><description>Summary</description></item></channel></rss>'

class RefreshTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name, value in [('DB_PATH', str(Path(temp.name) / 'test.db')), ('SOURCES', [('Test', 'https://example.com/rss')]), ('scrapling_fetcher', None), ('last_manual_refresh', 0)]:
            p = patch.object(app, name, value)
            p.start()
            self.addCleanup(p.stop)
        app.init_db()
        app.init_db()
        self.client = app.app.test_client()

    def test_network_timeout_recovers_with_retry(self):
        with patch.object(app.urllib.request, 'urlopen', side_effect=[TimeoutError(), io.BytesIO(RSS)]) as fetch, patch.object(app.time, 'sleep'), patch.object(app, 'refresh_github_trending', return_value=1):
            result = app.refresh_articles()
        self.assertEqual(result['inserted'], 1)
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(self.client.get('/api/status').json['sources'][0]['last_success_at'])

    def test_failure_preserves_success_time_and_articles(self):
        with patch.object(app.urllib.request, 'urlopen', return_value=io.BytesIO(RSS)), patch.object(app, 'refresh_github_trending', return_value=1):
            app.refresh_articles()
        before = self.client.get('/api/status').json
        with patch.object(app.urllib.request, 'urlopen', side_effect=TimeoutError('timeout')) as fetch, patch.object(app.time, 'sleep'), patch.object(app, 'refresh_github_trending', side_effect=TimeoutError('timeout')):
            result = app.refresh_articles()
        after = self.client.get('/api/status').json
        self.assertFalse(result['ok'])
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(after['last_refresh'], before['last_refresh'])
        self.assertEqual(after['total_articles'], 1)
        self.assertEqual(after['sources'][1]['last_success_at'], before['sources'][1]['last_success_at'])
        self.assertEqual(after['sources'][0]['ok'], 0)

    def test_retry_failed_skips_healthy_sources(self):
        with app.db_connect() as db:
            db.execute("INSERT INTO source_status (source, ok, message, fetched_at) VALUES ('Test', 1, '', 'old')")
            db.execute("INSERT INTO source_status (source, ok, message, fetched_at) VALUES ('GitHub Trending', 0, 'timeout', 'old')")
        with patch.object(app.urllib.request, 'urlopen', side_effect=AssertionError('healthy feed fetched')), patch.object(app, 'refresh_github_trending', return_value=2):
            response = self.client.post('/api/refresh', json={'failed_only': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['source'] for r in response.json['sources']], ['GitHub Trending'])

    def test_lock_applies_to_background_calls(self):
        app.refresh_lock.acquire()
        try:
            with self.assertRaises(RuntimeError):
                app.refresh_articles()
        finally:
            app.refresh_lock.release()

    def test_permanent_http_error_is_not_retried(self):
        error = urllib.error.HTTPError('https://example.com/rss', 404, 'not found', {}, None)
        with patch.object(app.urllib.request, 'urlopen', side_effect=error) as fetch, patch.object(app, 'refresh_github_trending', return_value=1):
            result = app.refresh_articles()
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result['failed_count'], 1)

    def test_invalid_feed_and_trending_preserve_old_snapshot(self):
        with app.db_connect() as db:
            db.execute("INSERT INTO github_trending (snapshot_date, rank, repo_name, url) VALUES ('2026-10-02', 1, 'old/repo', 'https://github.com/old/repo')")
        with patch.object(app.urllib.request, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(b'<html>unavailable</html>')):
            result = app.refresh_articles()
        self.assertFalse(result['ok'])
        self.assertEqual(self.client.get('/api/trending').json['items'][0]['repo_name'], 'old/repo')

    def test_legacy_status_migration_preserves_known_success(self):
        with app.db_connect() as db:
            db.execute('DROP TABLE source_status')
            db.execute("CREATE TABLE source_status (source TEXT PRIMARY KEY, ok INTEGER NOT NULL, message TEXT DEFAULT '', fetched_at TEXT NOT NULL)")
            db.execute("INSERT INTO source_status VALUES ('Test', 1, '', '2026-09-01T01:00:00+00:00')")
        app.init_db()
        app.init_db()
        item = self.client.get('/api/sources').json[0]
        self.assertEqual(item['last_success_at'], '2026-09-01T01:00:00+00:00')

    def test_invalid_request_is_rejected(self):
        self.assertEqual(self.client.post('/api/refresh', json=[]).status_code, 400)
        self.assertEqual(self.client.post('/api/refresh', json={'failed_only': 'yes'}).status_code, 400)

if __name__ == '__main__':
    unittest.main()
