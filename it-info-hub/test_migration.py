import sqlite3
import tempfile
import unittest
from pathlib import Path
import app


class MigrationTest(unittest.TestCase):
    # 確認舊資料庫升級後仍保留文章 ID、內容和分類。
    def test_old_articles_keep_identity_and_gain_category(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = app.DB_PATH
            self.addCleanup(setattr, app, "DB_PATH", previous)
            app.DB_PATH = str(Path(directory) / "legacy.db")
            with sqlite3.connect(app.DB_PATH) as db:
                db.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT UNIQUE NOT NULL, summary TEXT, source TEXT, published_at TEXT, fetched_at TEXT, image_url TEXT)")
                db.execute("INSERT INTO articles VALUES (42, 'Saved article', 'https://example.com/old', 'Original summary', 'GitHub Blog', '2026-09-01', '2026-09-01', '')")
            app.init_db()
            app.init_db()
            response = app.app.test_client().get('/api/articles')
            self.assertEqual(response.status_code, 200)
            rows = response.get_json()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['id'], 42)
            self.assertEqual(rows[0]['summary'], 'Original summary')
            self.assertEqual(rows[0].get('category'), 'Software')
            self.assertGreaterEqual(len(app.SOURCES), 60)
            self.assertEqual(app.app.test_client().get('/').status_code, 200)


if __name__ == '__main__':
    unittest.main()
