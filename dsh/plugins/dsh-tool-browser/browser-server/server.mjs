import http from 'node:http';
import { chromium } from 'playwright';

const PORT = process.env.BROWSER_PORT || 8731;
let browser = null;
const pages = []; // [{id, page}] — store the real Playwright Page object
let activeId = null;
const DEFAULT_TIMEOUT = 5000;

function send(res, code, obj){ const s=JSON.stringify(obj); res.writeHead(code,{ 'Content-Type':'application/json' }); res.end(s); }

async function ensure(res){ if(browser) return; try{ browser = await chromium.launch({ headless:true, args:['--no-sandbox','--disable-dev-shm-usage'] }); }catch(e){ if(res) send(res,500,{error:String(e)}); throw e; } }

const server = http.createServer(async (req,res)=>{
  try{
    if(req.method==='GET' && req.url==='/health'){ await ensure(res); const pageInfo=[]; for(const x of pages) pageInfo.push({id:x.id,title:await x.page.title(),url:x.page.url()}); send(res,200,{status:'ok',ready:!!browser,pages:pageInfo}); return; }
    let body=''; for await(const c of req) body+=c;
    let json={}; try{ json=body?JSON.parse(body):{};}catch(e){ send(res,400,{error:'bad json'}); return; }
    const path=req.url.split('?')[0];
    if((req.method==='GET'||req.method==='POST') && (path==='/list-pages'||path==='/url'||path==='/content-type')){ await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; send(res,200,{title:entry?await entry.page.title():'',url:entry?await entry.page.url():'',count:pages.length}); return; }
    if(req.method!=='POST'){ send(res,405,{error:'method not allowed'}); return; }
    const action=json.action||{};
    switch(path){
      case '/new': { await ensure(res); const pg=await browser.newPage(); const id=pages.length?Math.max(...pages.map(x=>x.id))+1:1; pages.push({id, page:pg}); activeId=id; send(res,201,{id,count:pages.length}); break; }
      case '/close-page': { if(action.id){ const i=pages.findIndex(x=>x.id===action.id); if(i>=0){ pages[i].page.close().catch(()=>{}); pages.splice(i,1); }} send(res,200,{count:pages.length}); break; }
      case '/goto': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page.goto(action.url||'', {waitUntil:action.waitUntil||'domcontentloaded', timeout}); send(res,200,{title:await entry.page.title(),url:await entry.page.url()}); break; }
      case '/title': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); send(res,200,{title:await entry.page.title()}); break; }
      case '/screenshot': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const buf=await entry.page.screenshot({ fullPage:!!action.fullPage }); send(res,200,{png:buf?buf.toString('base64'):'',type:'png'}); break; }
      case '/evaluate': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const expr=String(json.expression||action.expression||''); const r=await entry.page.evaluate((e)=>{ try{return (0,eval)(e);}catch(err){return String(err);} }, expr); send(res,200,{result:r}); break; }
      case '/click': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page.click(action.selector||'', {timeout}); send(res,200,{ok:true}); break; }
      case '/fill': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page.fill(action.selector||'', action.value||'', {timeout}); send(res,200,{ok:true}); break; }
      case '/type': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); await entry.page.fill(action.selector||'', action.value||''); send(res,200,{ok:true}); break; }
      case '/press': { await ensure(res); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); await entry.page.evaluate((k)=>{ window.dispatchEvent(new KeyboardEvent('keydown',{key:k})); window.dispatchEvent(new KeyboardEvent('keyup',{key:k})); }, action.key||''); send(res,200,{ok:true}); break; }
      default: send(res,400,{error:'unknown path '+path}); return;
    }
  }catch(e){ send(res,500,{error:String(e)}); }
});

server.listen(PORT, '0.0.0.0', ()=>{ console.log('browser-control listening on 0.0.0.0:'+PORT); });
