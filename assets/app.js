const menu=document.querySelector('.menu-toggle');
const nav=document.querySelector('#nav');
menu?.addEventListener('click',()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&nav?.classList.contains('open')){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.focus();}});
const filter=document.querySelector('[data-category-filter]');
filter?.addEventListener('change',()=>{document.querySelectorAll('[data-filter-items] > [data-topic]').forEach(el=>{el.hidden=filter.value!=='all'&&el.dataset.topic!==filter.value;});});
const query=new URLSearchParams(location.search).get('q')?.trim()||'';
const searchInput=document.querySelector('#search-q');
if(searchInput){
 searchInput.value=query;
 const results=document.querySelector('#search-results');const count=document.querySelector('#search-count');
 if(query){fetch('/assets/search-index.json').then(r=>r.json()).then(items=>{
  const terms=query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const found=items.filter(x=>terms.every(t=>(x.title+' '+x.summary+' '+x.topic+' '+x.type).toLocaleLowerCase().includes(t)));
  count.textContent=found.length?`${found.length} result${found.length===1?'':'s'} for “${query}”`:`No results for “${query}”. Try a broader topic such as home, travel or bills.`;
  results.replaceChildren(...found.map(x=>{let article=document.createElement('article');article.className='story-card';let kind=document.createElement('span');kind.className='kicker';kind.textContent=x.type;let h=document.createElement('h3');let a=document.createElement('a');a.href=x.url;a.textContent=x.title;h.append(a);let p=document.createElement('p');p.textContent=x.summary;article.append(kind,h,p);return article;}));
 }).catch(()=>{count.textContent='Search is unavailable right now. Browse the guides instead.';});}
}
