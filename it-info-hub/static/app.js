const $ = selector => document.querySelector(selector);

const articleRoot = $('#articles'), trendingRoot = $('#trending'), statusText = $('#status'), updatedText = $('#updated'), healthText = $('#source-health'), healthList = $('#source-health-list');
const releaseRoot = $('#releases'), releaseCount = $('#release-count');
const sourceDirectory = $('#source-directory-list');
const sourceSelect = $('#source'), categorySelect = $('#category'), refreshButton = $('#refresh'), searchInput = $('#search'), sortSelect = $('#sort'), favoritesOnly = $('#favorites'), unreadOnly = $('#unread-only');
const yearSelect = $('#year'), monthSelect = $('#month'), daySelect = $('#day');
const loaderOverlay = $('#loader-overlay');
const retryFailedButton = $('#retry-failed');
const sourceDrawer = $('#source-drawer-backdrop');
const openSourcesBtn = $('#open-sources-btn');
const closeDrawerBtn = $('#close-drawer-btn');

let articles = [], archive = [];
const favorites = new Set(JSON.parse(localStorage.getItem('itHubFavorites') || '[]'));
const readArticles = new Set(JSON.parse(localStorage.getItem('itHubRead') || '[]'));

function showLoader() {
  if (loaderOverlay) loaderOverlay.classList.add('active');
}

function hideLoader() {
  if (loaderOverlay) loaderOverlay.classList.remove('active');
}

// 統一處理 API 回應，避免 HTML 錯誤頁觸發 JSON 錯誤
async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) throw new Error(`API 回應格式錯誤（HTTP ${response.status}）`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `API 請求失敗（HTTP ${response.status}）`);
  return data;
}

// 將 RSS 摘要轉成安全純文字
function textOnly(value) {
  if (!value) return '';
  const node = document.createElement('div');
  node.innerHTML = value;
  return (node.textContent || '').trim();
}

// 使用台北時區格式化文章日期
function dateLabel(iso) {
  if (!iso) return '';
  return new Intl.DateTimeFormat('zh-TW', { timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(iso));
}

// 只有年月日都選取時，才組合成 API 日期參數
function selectedDate() {
  return yearSelect && yearSelect.value && monthSelect && monthSelect.value && daySelect && daySelect.value 
    ? `${yearSelect.value}-${monthSelect.value}-${daySelect.value}` : '';
}

// 重建下拉選單
function fillSelect(select, label, values, selected = '') {
  if (!select) return;
  select.replaceChildren(new Option(label, ''));
  values.forEach(item => select.add(new Option(item.label, item.value)));
  if ([...select.options].some(o => o.value === selected)) select.value = selected;
}

function updateArchiveControls(preferred = '') {
  const dates = archive.map(item => item.date), oldYear = preferred.slice(0, 4) || (yearSelect ? yearSelect.value : '');
  const years = [...new Set(dates.map(date => date.slice(0, 4)))].sort().reverse();
  fillSelect(yearSelect, '全部年份', years.map(value => ({ value, label: `${value} 年` })), oldYear);
  const oldMonth = preferred.slice(5, 7) || (monthSelect ? monthSelect.value : '');
  const months = [...new Set(dates.filter(date => !yearSelect?.value || date.startsWith(yearSelect.value)).map(date => date.slice(5, 7)))].sort().reverse();
  fillSelect(monthSelect, '全部月份', months.map(value => ({ value, label: `${Number(value)} 月` })), oldMonth);
  const oldDay = preferred.slice(8, 10) || (daySelect ? daySelect.value : ''), prefix = yearSelect?.value && monthSelect?.value ? `${yearSelect.value}-${monthSelect.value}-` : '';
  const days = archive.filter(item => !prefix || item.date.startsWith(prefix));
  fillSelect(daySelect, '全部日期', days.map(item => ({ value: item.date.slice(8, 10), label: `${Number(item.date.slice(8, 10))} 日（${item.count} 篇）` })), oldDay);
}

function getCategoryClass(cat = '') {
  const lower = (cat || '').toLowerCase();
  if (lower.includes('security') || lower.includes('安')) return 'security';
  if (lower.includes('ai') || lower.includes('智能')) return 'ai';
  if (lower.includes('cloud') || lower.includes('雲')) return 'cloud';
  if (lower.includes('release') || lower.includes('更新')) return 'release';
  return 'software';
}

function isRelease(item) {
  return (item.source || '').endsWith(' Releases') || (item.category || '').includes('Release');
}

function makeCard(item, compact = false) {
  const card = document.createElement('article');
  if (compact) card.classList.add('release-item');
  if (readArticles.has(item.url)) card.classList.add('read');

  const readMark = document.createElement('span');
  readMark.className = 'read-mark';
  readMark.title = '未讀文章';
  card.appendChild(readMark);

  const media = document.createElement('div');
  media.className = 'media';
  if (item.image_url) {
    const image = document.createElement('img');
    image.src = item.image_url;
    image.alt = '';
    image.loading = 'lazy';
    image.referrerPolicy = 'no-referrer';
    image.addEventListener('error', () => media.classList.add('fallback'));
    media.appendChild(image);
  } else {
    media.classList.add('fallback');
  }

  const body = document.createElement('div');
  body.className = 'card-body';
  
  const top = document.createElement('div');
  top.className = 'card-top';

  const badgeGroup = document.createElement('div');
  badgeGroup.className = 'badge-group';

  const source = document.createElement('span');
  source.className = 'source-badge';
  source.textContent = item.source || '';
  badgeGroup.appendChild(source);

  if (item.category) {
    const catBadge = document.createElement('span');
    catBadge.className = `cat-badge ${getCategoryClass(item.category)}`;
    catBadge.textContent = item.category;
    badgeGroup.appendChild(catBadge);
  }

  const favorite = document.createElement('button');
  favorite.className = 'favorite-btn';
  favorite.ariaLabel = favorites.has(item.url) ? '取消收藏文章' : '收藏文章';
  favorite.setAttribute('aria-pressed', String(favorites.has(item.url)));
  favorite.textContent = favorites.has(item.url) ? '★' : '☆';
  favorite.addEventListener('click', (e) => {
    e.stopPropagation();
    favorites.has(item.url) ? favorites.delete(item.url) : favorites.add(item.url);
    localStorage.setItem('itHubFavorites', JSON.stringify([...favorites]));
    render();
  });

  top.append(badgeGroup, favorite);

  const title = document.createElement('h3');
  const link = document.createElement('a');
  link.href = item.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = item.title || '';
  link.addEventListener('click', () => {
    readArticles.add(item.url);
    localStorage.setItem('itHubRead', JSON.stringify([...readArticles]));
    card.classList.add('read');
  });
  title.appendChild(link);

  const summaryText = textOnly(item.summary);
  const summary = document.createElement('p');
  summary.textContent = summaryText.length > 260 ? summaryText.slice(0, 260) + '…' : (summaryText || '點擊標題查看完整內容。');

  const actions = document.createElement('div');
  actions.className = 'card-actions';

  const viewBtn = document.createElement('a');
  viewBtn.className = 'uiverse-btn';
  viewBtn.style.padding = '0.4em 0.9em';
  viewBtn.style.fontSize = '12px';
  viewBtn.href = item.url;
  viewBtn.target = '_blank';
  viewBtn.rel = 'noopener noreferrer';
  viewBtn.addEventListener('click', () => { readArticles.add(item.url); localStorage.setItem('itHubRead', JSON.stringify([...readArticles])); card.classList.add('read'); });
  viewBtn.innerHTML = `<span>觀看原文</span>`;

  const translateBtn = document.createElement('button');
  translateBtn.className = 'translate-btn';
  translateBtn.textContent = item.translation ? '顯示原文' : '翻譯成繁體中文';

  actions.append(viewBtn, translateBtn);

  const translation = document.createElement('div');
  translation.className = 'translation-box';
  const translatedTitle = document.createElement('h4'), translatedSummary = document.createElement('p');
  
  if (item.translation) {
    translatedTitle.textContent = item.translation.title;
    translatedSummary.textContent = item.translation.summary || '沒有可翻譯的摘要。';
    translation.append(translatedTitle, translatedSummary);
  } else {
    translation.hidden = true;
  }

  translateBtn.addEventListener('click', async () => {
    if (item.translation) {
      translation.hidden = !translation.hidden;
      translateBtn.textContent = translation.hidden ? '翻譯成繁體中文' : '顯示原文';
      return;
    }
    translateBtn.disabled = true;
    translateBtn.textContent = '翻譯中…';
    try {
      const result = await fetchJson('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: item.title, summary: item.summary })
      });
      item.translation = result;
      translatedTitle.textContent = result.title;
      translatedSummary.textContent = result.summary || '沒有可翻譯的摘要。';
      translation.replaceChildren(translatedTitle, translatedSummary);
      translation.hidden = false;
      translateBtn.textContent = '顯示原文';
    } catch (error) {
      translateBtn.textContent = error.message || '翻譯失敗';
    } finally {
      translateBtn.disabled = false;
    }
  });

  const published = document.createElement('time');
  published.dateTime = item.published_at;
  published.textContent = timeLabel(item.published_at);
  body.append(top, title, summary, published, actions, translation);
  if (!compact) card.append(media);
  card.append(body);
  return card;
}

function render() {
  if (!articleRoot) return;
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
  const filtered = articles.filter(i => !sourceSelect?.value || i.source === sourceSelect.value)
    .filter(i => !categorySelect?.value || i.category === categorySelect.value)
    .filter(i => !favoritesOnly?.checked || favorites.has(i.url))
    .filter(i => !unreadOnly?.checked || !readArticles.has(i.url))
    .filter(i => {
      if (!query) return true;
      const titleMatch = (i.title || '').toLowerCase().includes(query);
      const summaryMatch = textOnly(i.summary).toLowerCase().includes(query);
      const sourceMatch = (i.source || '').toLowerCase().includes(query);
      return titleMatch || summaryMatch || sourceMatch;
    })
    .sort((a, b) => ((sortSelect?.value === 'oldest') ? 1 : -1) * (new Date(a.published_at) - new Date(b.published_at)));

  const releases = filtered.filter(isRelease);
  if (releaseRoot) {
    releaseRoot.replaceChildren(...releases.map(item => makeCard(item, true)));
    if (!releases.length) {
      const empty = document.createElement('p');
      empty.className = 'panel-empty';
      empty.textContent = '目前篩選條件沒有版本更新';
      releaseRoot.append(empty);
    }
  }
  if (releaseCount) releaseCount.textContent = `${releases.length} 筆`;
  const news = filtered.filter(item => !isRelease(item));
  const groups = news.reduce((all, item) => {
    const key = dateLabel(item.published_at) || '未分類日期';
    if (!all[key]) all[key] = [];
    all[key].push(item);
    return all;
  }, {});

  articleRoot.replaceChildren();

  if (!news.length) {
    const empty = document.createElement('section');
    empty.className = 'empty-state';
    empty.style.textAlign = 'center';
    empty.style.padding = '60px 20px';
    empty.innerHTML = `
      <div style="font-size: 42px; margin-bottom: 12px; color: var(--text-gold);">⌕</div>
      <h2 style="font-family: 'Cinzel', serif; font-size: 24px; margin-bottom: 8px;">沒有符合條件的新聞</h2>
      <p style="color: var(--text-secondary);">版本更新請查看右側列表，或調整搜尋與篩選條件。</p>
      <button class="uiverse-btn secondary" style="margin-top: 18px;" id="reset-filters">
        <span>重設篩選條件</span>
      </button>
    `;
    const resetBtn = empty.querySelector('#reset-filters');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        if (sourceSelect) sourceSelect.value = '';
        if (categorySelect) categorySelect.value = '';
        if (sortSelect) sortSelect.value = 'newest';
        if (favoritesOnly) favoritesOnly.checked = false;
        if (unreadOnly) unreadOnly.checked = false;
        if (yearSelect) yearSelect.value = '';
        if (monthSelect) monthSelect.value = '';
        if (daySelect) daySelect.value = '';
        updateArchiveControls();
        loadArticles();
      });
    }
    articleRoot.appendChild(empty);
    if (statusText) statusText.textContent = `顯示 ${news.length} 篇新聞、${releases.length} 筆版本更新`;
    return;
  }

  Object.entries(groups).forEach(([date, items]) => {
    const group = document.createElement('div');
    group.className = 'day-group';
    const heading = document.createElement('h2');
    heading.textContent = date;
    const count = document.createElement('small');
    count.textContent = `${items.length} 篇`;
    heading.appendChild(count);
    const grid = document.createElement('div');
    grid.className = 'grid';
    items.forEach(item => grid.appendChild(makeCard(item)));
    group.append(heading, grid);
    articleRoot.appendChild(group);
  });

  if (statusText) statusText.textContent = filtered.length ? `顯示 ${news.length} 篇新聞、${releases.length} 筆版本更新` : '沒有符合條件的資訊';
}

async function loadArticles() {
  showLoader();
  try {
    const date = selectedDate();
    articles = await fetchJson(`/api/articles${date ? `?date=${date}` : ''}`);
    const currentSource = sourceSelect ? sourceSelect.value : '';
    const sourceNames = sourceDirectory?.dataset.sources ? JSON.parse(sourceDirectory.dataset.sources) : [...new Set(articles.map(i => i.source))];
    fillSelect(sourceSelect, '全部來源', sourceNames.sort().map(value => ({ value, label: value })), currentSource);
    const currentCategory = categorySelect ? categorySelect.value : '';
    const categories = [...new Set(articles.map(i => i.category).filter(Boolean))].sort();
    fillSelect(categorySelect, '全部分類', categories.map(value => ({ value, label: value })), currentCategory);
    render();
    await loadTrending(date);
  } catch (err) {
    console.error("載入文章失敗:", err);
  } finally {
    hideLoader();
  }
}

function timeLabel(value) {
  return value ? new Date(value).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' }) : '尚無成功紀錄';
}

async function loadSources() {
  try {
    const sources = await fetchJson('/api/sources');
    if (sourceDirectory) {
      sourceDirectory.dataset.sources = JSON.stringify(sources.map(item => item.source));
      sourceDirectory.replaceChildren();
      sources.forEach(item => {
        const row = document.createElement('div');
        row.className = 'source-directory-item';
        const name = document.createElement('strong');
        name.textContent = item.source;
        const meta = document.createElement('small');
        meta.textContent = `${item.category} · ${item.count} 篇 · ${item.ok === null ? '尚未更新' : item.ok ? '正常' : '失敗'}`;
        const detail = document.createElement('small');
        detail.textContent = `最後成功：${timeLabel(item.last_success_at)}${item.ok === 0 ? ` · 原因：${item.message}` : ''}`;
        row.append(name, meta, detail);
        sourceDirectory.append(row);
      });
    }
  } catch (e) {
    console.error("載入來源失敗:", e);
  }
}

async function loadArchive() {
  try {
    archive = await fetchJson('/api/archive');
    updateArchiveControls(archive[0]?.date || '');
  } catch (e) {
    console.error("載入歸檔失敗:", e);
  }
}

async function loadTrending(date = '') {
  try {
    if (!trendingRoot) return;
    const data = await fetchJson(`/api/trending${date ? `?date=${date}` : ''}`);
    trendingRoot.replaceChildren();
    if (!data.items || !data.items.length) return;
    const heading = document.createElement('h2');
    heading.textContent = 'GitHub Trending';
    const dateText = document.createElement('small');
    dateText.textContent = data.date;
    const header = document.createElement('div');
    header.className = 'panel-heading';
    header.append(heading, dateText);
    const list = document.createElement('div');
    list.className = 'trending-list';
    data.items.slice(0, 5).forEach(item => {
      const row = document.createElement('a');
      row.className = 'trending-item';
      row.href = item.url;
      row.target = '_blank';
      row.rel = 'noopener noreferrer';
      const rank = document.createElement('b');
      rank.textContent = `#${item.rank}`;
      const detail = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = item.repo_name;
      const meta = document.createElement('small');
      meta.textContent = `${item.language || 'Code'} · ★ ${item.stars || 0}`;
      detail.append(name, meta);
      row.append(rank, detail);
      list.appendChild(row);
    });
    trendingRoot.append(header, list);
  } catch (e) {
    console.error("載入 Trending 失敗:", e);
  }
}

async function loadStatus() {
  try {
    const data = await fetchJson('/api/status');
    if (updatedText) updatedText.textContent = `最後取得資料：${timeLabel(data.last_refresh)} · 累計 ${data.total_articles} 篇`;
    if (data.refresh_outcome === 'failed' && statusText) statusText.textContent = '本次更新失敗，正在顯示上次資料';
    const failed = (data.sources || []).filter(i => !i.ok);
    if (retryFailedButton) retryFailedButton.hidden = !failed.length;
    if (healthText) {
      healthText.textContent = failed.length ? `${failed.length} 個來源讀取失敗` : data.sources.length ? `${data.sources.length} 個來源正常` : '';
      healthText.className = failed.length ? 'health-error' : 'health-ok';
    }
    if (healthList) {
      healthList.replaceChildren();
      failed.forEach(item => {
        const row = document.createElement('div');
        const source = document.createElement('strong');
        source.textContent = item.source;
        const reason = document.createElement('span');
        reason.textContent = `原因：${item.message || '未知錯誤'}`;
        const fetched = document.createElement('small');
        fetched.textContent = item.fetched_at ? `最後嘗試：${new Date(item.fetched_at).toLocaleString('zh-TW')}` : '尚未嘗試';
        const success = document.createElement('small');
        success.textContent = `最後成功：${timeLabel(item.last_success_at)}`;
        row.append(source, reason, fetched, success);
        healthList.append(row);
      });
    }
  } catch (e) {
    console.error("載入 Status 失敗:", e);
  }
}

// Drawer Open / Close Event Listeners
if (openSourcesBtn && sourceDrawer) {
  openSourcesBtn.addEventListener('click', () => sourceDrawer.classList.remove('hidden'));
}
if (closeDrawerBtn && sourceDrawer) {
  closeDrawerBtn.addEventListener('click', () => sourceDrawer.classList.add('hidden'));
}
if (sourceDrawer) {
  sourceDrawer.addEventListener('click', (e) => {
    if (e.target === sourceDrawer) sourceDrawer.classList.add('hidden');
  });
}

if (yearSelect) yearSelect.addEventListener('change', () => { updateArchiveControls(); loadArticles(); });
if (monthSelect) monthSelect.addEventListener('change', () => { updateArchiveControls(); loadArticles(); });
if (daySelect) daySelect.addEventListener('change', loadArticles);
if (sourceSelect) sourceSelect.addEventListener('change', render);
if (categorySelect) categorySelect.addEventListener('change', render);
if (searchInput) searchInput.addEventListener('input', render);
if (sortSelect) sortSelect.addEventListener('change', render);
if (favoritesOnly) favoritesOnly.checked = false;
if (favoritesOnly) favoritesOnly.addEventListener('change', render);
if (unreadOnly) unreadOnly.checked = false;
if (unreadOnly) unreadOnly.addEventListener('change', render);

async function runRefresh(failedOnly = false) {
  showLoader();
  if (refreshButton) refreshButton.setAttribute('aria-busy', 'true');
  if (refreshButton) refreshButton.disabled = true;
  if (retryFailedButton) retryFailedButton.disabled = true;
  if (statusText) statusText.textContent = failedOnly ? '正在重抓失敗來源…' : '正在更新所有來源…';
  try {
    const result = await fetchJson('/api/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ failed_only: failedOnly })
    });
    await loadArchive();
    await loadArticles();
    await loadSources();
    await loadStatus();
    if (statusText) statusText.textContent = !result.ok
      ? '本次更新失敗，正在顯示上次資料'
      : !result.sources.length ? '沒有需要重抓的失敗來源'
      : result.failed_count ? `部分更新完成：新增 ${result.inserted} 篇，${result.failed_count} 個來源仍失敗`
      : `更新完成：新增 ${result.inserted} 篇，GitHub 排行 ${result.ranking_count} 筆`;
  } catch (error) {
    if (statusText) statusText.textContent = error.message || '更新失敗';
  } finally {
    if (refreshButton) { refreshButton.disabled = false; refreshButton.removeAttribute('aria-busy'); }
    if (retryFailedButton) retryFailedButton.disabled = false;
    hideLoader();
  }
}
if (refreshButton) refreshButton.addEventListener('click', () => runRefresh());
if (retryFailedButton) retryFailedButton.addEventListener('click', () => runRefresh(true));

(async () => {
  showLoader();
  try {
    await loadArchive();
    await loadSources();
    await Promise.all([loadArticles(), loadStatus()]);
  } catch (err) {
    console.error("初始化失敗:", err);
    if (statusText) statusText.textContent = '讀取失敗，請稍後重試';
  } finally {
    hideLoader();
  }
})();
