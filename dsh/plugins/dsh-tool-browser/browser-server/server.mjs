import http from 'node:http';
import { chromium } from 'playwright';

const PORT = process.env.BROWSER_PORT || 8731;
let browser = null;
const pages = []; // [{id, page}] — store the real Playwright Page object
let activeId = null;
const DEFAULT_TIMEOUT = 5000;

function send(res, code, obj){ const s=JSON.stringify(obj); res.writeHead(code,{ 'Content-Type':'application/json' }); res.end(s); }

async function ensure(){ if(browser) return; try{ browser = await chromium.launch({ headless:true, args:['--no-sandbox','--disable-dev-shm-usage'] }); }catch(e){ send(res,500,{error:String(e)}); process.exit(1);} }

const server = http.createServer(async (req,res)=>{
  try{
    if(req.method==='GET' && req.url==='/health'){ await ensure(); send(res,200,{status:'ok',ready:!!browser,pages}); return; }
    let body=''; for await(const c of req) body+=c;
    let json={}; try{ json=body?JSON.parse(body):{};}catch(e){ send(res,400,{error:'bad json'}); return; }
    const path=req.url.split('?')[0];
    if(req.method==='GET' && (path==='/list-pages'||path==='/url'||path==='/content-type')){ await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; send(res,200,{title:entry?entry.page.title():'',url:entry?entry.page.url():'',count:pages.length}); return; }
    if(req.method!=='POST'){ send(res,405,{error:'method not allowed'}); return; }
    const action=json.action||{};
    switch(path){
      case '/new': { await ensure(); const pg=await browser.newPage(); pages.push({id:++activeId, page:pg}); activeId=pages.length; send(res,201,{id:activeId,count:pages.length}); break; }
      case '/close-page': { if(action.id){ const i=pages.findIndex(x=>x.id===action.id); if(i>=0){ pages[i].page.close().catch(()=>{}); pages.splice(i,1); }} send(res,200,{count:pages.length}); break; }
      case '/goto': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page['goto'](action.url||'', action.waitUntil||'domcontentloaded', {timeout}); send(res,200,{title:await entry.page.title(),url:await entry.page.url()}); break; }
      case '/title': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); send(res,200,{title:await entry.page.title()}); break; }
      case '/screenshot': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const buf=await entry.page.screenshot({ fullPage:!!json.fullPage }); send(res,200,{png:buf?buf.toString('base64'):'',type:'png'}); break; }
      case '/evaluate': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const expr=String(json.expression||''); const r=await entry.page.evaluate((e)=>{ try{return (0,eval)(e);}catch(err){return String(err);} }, expr); send(res,200,{result:String(r)}); break; }
      case '/click': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page['click'](action.selector||'', {timeout}); send(res,200,{ok:true}); break; }
      case '/fill': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); const timeout=action.timeout||DEFAULT_TIMEOUT; await entry.page.fill(action.selector||'', action.value||'', {timeout}); send(res,200,{ok:true}); break; }
      case '/type': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); await entry.page.fill(action.selector||'', action.value||''); send(res,200,{ok:true}); break; }
      case '/press': { await ensure(); const entry=pages.find(x=>x.id===activeId)||pages[0]; if(!entry) throw new Error('no page'); await entry.page.evaluate((k)=>{ window.dispatchEvent(new KeyboardEvent('keydown',{key:k})); window.dispatchEvent(new KeyboardEvent('keyup',{key:k})); }, action.key||''); send(res,200,{ok:true}); break; }
      default: send(res,400,{error:'unknown path '+path}); return;
    }
  }catch(e){ send(res,500,{error:String(e)}); }
});

server.listen(PORT, '0.0.0.0', ()=>{ console.log('browser-control listening on 0.0.0.0:'+PORT); });