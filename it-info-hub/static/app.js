const $ = selector => document.querySelector(selector);
const articleRoot=$('#articles'), trendingRoot=$('#trending'), statusText=$('#status'), updatedText=$('#updated'), healthText=$('#source-health');
const sourceSelect=$('#source'), refreshButton=$('#refresh'), searchInput=$('#search'), sortSelect=$('#sort'), favoritesOnly=$('#favorites');
const yearSelect=$('#year'), monthSelect=$('#month'), daySelect=$('#day');
let articles=[], archive=[];
const favorites=new Set(JSON.parse(localStorage.getItem('itHubFavorites')||'[]'));
const readArticles=new Set(JSON.parse(localStorage.getItem('itHubRead')||'[]'));

function textOnly(value){const node=document.createElement('div');node.innerHTML=value||'';return(node.textContent||'').trim().slice(0,260)}
function dateLabel(iso){return new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(iso))}
function selectedDate(){return yearSelect.value&&monthSelect.value&&daySelect.value?`${yearSelect.value}-${monthSelect.value}-${daySelect.value}`:''}
function fillSelect(select,label,values,selected=''){select.replaceChildren(new Option(label,''));values.forEach(item=>select.add(new Option(item.label,item.value)));if([...select.options].some(o=>o.value===selected))select.value=selected}

function updateArchiveControls(preferred=''){
  const dates=archive.map(item=>item.date), oldYear=preferred.slice(0,4)||yearSelect.value;
  const years=[...new Set(dates.map(date=>date.slice(0,4)))].sort().reverse();
  fillSelect(yearSelect,'全部年份',years.map(value=>({value,label:`${value} 年`})),oldYear);
  const oldMonth=preferred.slice(5,7)||monthSelect.value;
  const months=[...new Set(dates.filter(date=>!yearSelect.value||date.startsWith(yearSelect.value)).map(date=>date.slice(5,7)))].sort().reverse();
  fillSelect(monthSelect,'全部月份',months.map(value=>({value,label:`${Number(value)} 月`})),oldMonth);
  const oldDay=preferred.slice(8,10)||daySelect.value, prefix=yearSelect.value&&monthSelect.value?`${yearSelect.value}-${monthSelect.value}-`:'';
  const days=archive.filter(item=>!prefix||item.date.startsWith(prefix));
  fillSelect(daySelect,'全部日期',days.map(item=>({value:item.date.slice(8,10),label:`${Number(item.date.slice(8,10))} 日（${item.count} 篇）`})),oldDay);
}

function makeCard(item){
  const card=document.createElement('article');if(readArticles.has(item.url))card.classList.add('read');
  const media=document.createElement('div');media.className='media';
  if(item.image_url){const image=document.createElement('img');image.src=item.image_url;image.alt='';image.loading='lazy';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>media.classList.add('fallback'));media.appendChild(image)}else media.classList.add('fallback');
  const body=document.createElement('div');body.className='card-body';const top=document.createElement('div');top.className='card-top';
  const source=document.createElement('span');source.className='source';source.textContent=item.source;
  const favorite=document.createElement('button');favorite.className='favorite';favorite.ariaLabel='收藏文章';favorite.textContent=favorites.has(item.url)?'★':'☆';
  favorite.addEventListener('click',()=>{favorites.has(item.url)?favorites.delete(item.url):favorites.add(item.url);localStorage.setItem('itHubFavorites',JSON.stringify([...favorites]));render()});
  top.append(source,favorite);const title=document.createElement('h3'),link=document.createElement('a');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title;
  link.addEventListener('click',()=>{readArticles.add(item.url);localStorage.setItem('itHubRead',JSON.stringify([...readArticles]));card.classList.add('read')});title.appendChild(link);
  const summary=document.createElement('p');summary.textContent=textOnly(item.summary)||'點擊標題查看完整內容。';body.append(top,title,summary);card.append(media,body);return card;
}

function render(){
  const query=searchInput.value.trim().toLocaleLowerCase('zh-TW');
  const filtered=articles.filter(i=>!sourceSelect.value||i.source===sourceSelect.value).filter(i=>!favoritesOnly.checked||favorites.has(i.url))
    .filter(i=>!query||`${i.title} ${textOnly(i.summary)}`.toLocaleLowerCase('zh-TW').includes(query))
    .sort((a,b)=>(sortSelect.value==='oldest'?1:-1)*(new Date(a.published_at)-new Date(b.published_at)));
  const groups=filtered.reduce((all,item)=>{const key=dateLabel(item.published_at);(all[key]||=[]).push(item);return all},{});
  articleRoot.replaceChildren();
  Object.entries(groups).forEach(([date,items])=>{const group=document.createElement('div');group.className='day-group';const heading=document.createElement('h2');heading.textContent=date;const count=document.createElement('small');count.textContent=`${items.length} 篇`;heading.appendChild(count);const grid=document.createElement('div');grid.className='grid';items.forEach(item=>grid.appendChild(makeCard(item)));group.append(heading,grid);articleRoot.appendChild(group)});
  statusText.textContent=filtered.length?`顯示 ${filtered.length} 篇資訊`:'沒有符合條件的資訊';
}

async function loadArticles(){
  const date=selectedDate(),response=await fetch(`/api/articles${date?`?date=${date}`:''}`);if(!response.ok)throw new Error('資訊讀取失敗');articles=await response.json();
  const current=sourceSelect.value;fillSelect(sourceSelect,'全部來源',[...new Set(articles.map(i=>i.source))].sort().map(value=>({value,label:value})),current);render();await loadTrending(date);
}
async function loadArchive(){const response=await fetch('/api/archive');archive=await response.json();updateArchiveControls(archive[0]?.date||'')}
async function loadTrending(date=''){
  const response=await fetch(`/api/trending${date?`?date=${date}`:''}`),data=await response.json();trendingRoot.replaceChildren();if(!data.items.length)return;
  const heading=document.createElement('h2');heading.textContent=`GitHub Trending · ${data.date}`;const list=document.createElement('div');list.className='ranking-list';
  data.items.slice(0,10).forEach(item=>{const row=document.createElement('a');row.className='ranking-item';row.href=item.url;row.target='_blank';row.rel='noopener noreferrer';const rank=document.createElement('b');rank.textContent=`#${item.rank}`;const info=document.createElement('span'),name=document.createElement('strong'),meta=document.createElement('small');name.textContent=item.repo_name;meta.textContent=[item.language,item.stars&&`★ ${item.stars}`].filter(Boolean).join(' · ');info.append(name,meta);row.append(rank,info);list.appendChild(row)});trendingRoot.append(heading,list);
}
async function loadStatus(){const response=await fetch('/api/status'),data=await response.json();updatedText.textContent=data.last_refresh?`最後更新：${new Date(data.last_refresh).toLocaleString('zh-TW')} · 累計 ${data.total_articles} 篇`:'尚未更新';const failed=data.sources.filter(i=>!i.ok);healthText.textContent=failed.length?`${failed.length} 個來源讀取失敗`:data.sources.length?`${data.sources.length} 個來源正常`:'';healthText.className=failed.length?'health-error':'health-ok'}

yearSelect.addEventListener('change',()=>{updateArchiveControls();loadArticles()});monthSelect.addEventListener('change',()=>{updateArchiveControls();loadArticles()});daySelect.addEventListener('change',loadArticles);
sourceSelect.addEventListener('change',render);searchInput.addEventListener('input',render);sortSelect.addEventListener('change',render);favoritesOnly.addEventListener('change',render);
refreshButton.addEventListener('click',async()=>{refreshButton.disabled=true;statusText.textContent='正在更新所有來源…';try{const response=await fetch('/api/refresh',{method:'POST'}),result=await response.json();if(!response.ok)throw new Error(result.error||'更新失敗');await loadArchive();await loadArticles();await loadStatus();statusText.textContent=`更新完成：新增 ${result.inserted} 篇，GitHub 排行 ${result.ranking_count} 筆`}catch(error){statusText.textContent=error.message||'更新失敗'}finally{refreshButton.disabled=false}});
(async()=>{try{await loadArchive();await Promise.all([loadArticles(),loadStatus()])}catch{statusText.textContent='讀取失敗，請稍後重試'}})();
