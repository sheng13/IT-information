const articleRoot = document.querySelector('#articles');
const statusText = document.querySelector('#status');
const sourceSelect = document.querySelector('#source');
const refreshButton = document.querySelector('#refresh');
let articles = [];

function textOnly(html) {
  const node = document.createElement('div');
  node.innerHTML = html || '';
  return (node.textContent || '').trim().slice(0, 220);
}

function dateLabel(iso) {
  return new Intl.DateTimeFormat('zh-TW', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(new Date(iso));
}

function render() {
  const selected = sourceSelect.value;
  const filtered = articles.filter(item => !selected || item.source === selected);
  const groups = Object.groupBy
    ? Object.groupBy(filtered, item => dateLabel(item.published_at))
    : filtered.reduce((all, item) => {
        const key = dateLabel(item.published_at);
        (all[key] ||= []).push(item);
        return all;
      }, {});

  articleRoot.innerHTML = '';
  for (const [date, items] of Object.entries(groups)) {
    const group = document.createElement('div');
    group.className = 'day-group';
    group.innerHTML = `<h2>${date}<small>${items.length} 则</small></h2>`;
    const grid = document.createElement('div');
    grid.className = 'grid';
    for (const item of items) {
      const card = document.createElement('article');
      card.innerHTML = `
        <span class="source">${item.source}</span>
        <h3><a href="${item.url}" target="_blank" rel="noopener noreferrer"></a></h3>
        <p></p>`;
      card.querySelector('a').textContent = item.title;
      card.querySelector('p').textContent = textOnly(item.summary) || '点击标题查看完整内容。';
      grid.appendChild(card);
    }
    group.appendChild(grid);
    articleRoot.appendChild(group);
  }
  statusText.textContent = filtered.length ? `最近 7 天共 ${filtered.length} 则资讯` : '最近 7 天暂时没有资讯';
}

async function loadArticles() {
  const response = await fetch('/api/articles');
  if (!response.ok) throw new Error('读取失败');
  articles = await response.json();
  const sources = [...new Set(articles.map(item => item.source))].sort();
  sourceSelect.innerHTML = '<option value="">全部来源</option>' +
    sources.map(source => `<option value="${source}">${source}</option>`).join('');
  render();
}

sourceSelect.addEventListener('change', render);
refreshButton.addEventListener('click', async () => {
  refreshButton.disabled = true;
  statusText.textContent = '正在更新…';
  try {
    await fetch('/api/refresh', {method: 'POST'});
    await loadArticles();
  } catch (error) {
    statusText.textContent = '更新失败，请检查服务器网络';
  } finally {
    refreshButton.disabled = false;
  }
});

loadArticles().catch(() => { statusText.textContent = '读取失败，请稍后重试'; });
