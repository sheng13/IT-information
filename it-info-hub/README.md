# IT Info Hub

每天 09:00（Asia/Taipei）抓取資訊並永久保存，以年、月、日瀏覽歷史資料。

功能包含多個 IT RSS 來源、GitHub Trending 每日排行、文章圖片、年月日歸檔、來源篩選、關鍵字搜尋、排序、收藏、已讀狀態及來源健康狀態。文章沒有圖片時會自動顯示預設圖。

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

打开 `http://服务器IP:5001/`。


## 合併版與 Docker 更新

此目錄整合新版的 34 個來源、分類篩選及 Scrapling 補充抓取，保留原本 Docker 部署。
舊文章首次啟動會自動新增並補上分類，不變更文章 ID 或網址。
Docker 使用 `DB_PATH=/app/data/it_info.db`，資料保存在 `it_info_data` volume。
直接執行 `python app.py` 則預設使用專案內的 `it_info.db`。

首次從舊容器升級前，必須先停止容器，備份 `/app/it_info.db`，再把備份複製至原容器的 `/app/data/it_info.db`；之後才能重建容器。
完成首次遷移後，往後更新請在本目錄執行：

```bash
docker compose up -d --build
docker compose logs --tail=50 -f
```

不要執行 `docker compose down -v`，以免刪除文章資料。
啟動後先監聽 5001，10 秒後背景抓取；來源目錄固定列出所有設定來源。

驗證舊資料升級：`python -m unittest test_migration`。

## 抓取失敗處理

RSS 與 GitHub Trending 的暫時性網路錯誤最多嘗試 3 次，每次請求逾時 20 秒，重試間隔 1、2 秒。網址不存在或格式錯誤直接記錄失敗；圖片補抓失敗仍保存文章。
來源健康度顯示錯誤原因與最後成功時間，可用「重抓失敗來源」只更新失敗項目。手動更新間隔至少 60 秒，啟動、排程與手動更新共用鎖。
全部失敗不推進最後取得資料時間，畫面保留舊資料並顯示失敗提示。舊來源狀態自動新增最後成功欄位，舊失敗紀錄沒有可推算的成功時間，顯示尚無成功紀錄。

驗證：`python -m pytest`（測試使用暫存資料庫，不連線外部來源）。
