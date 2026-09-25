#!/usr/bin/env node
// Prezi (view pública) -> frames PNG + manifest.json, via Playwright headless Chromium.
// Uso: node capture.mjs [URL] [DIR_SAIDA]. Sem args: view de referência e /tmp/prezi2pdf/pages.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// Esta instalação distribui Playwright em node_modules/playwright; torná-lo importável de qualquer cwd.
// NODE_PATH precisa estar definido antes do processo iniciar para o require() padrão funcionar,
// portanto também tentamos os roots explicitamente.
const moduleRoots=[];
const addModuleRoot=root=>{
  if(root && !moduleRoots.includes(root)) moduleRoots.push(root);
};
for(const root of (process.env.PLAYWRIGHT_NODE_MODULES||'').split(path.delimiter)) addModuleRoot(root);
for(const root of (process.env.NODE_PATH||'').split(path.delimiter)) addModuleRoot(root);
for(let cursor=__dirname, depth=0; depth<12; depth++, cursor=path.dirname(cursor)){
  addModuleRoot(path.join(cursor,'node_modules'));
}
for(const root of ['/usr/lib/chatgpt/resources/cua_node/lib/node_modules','/usr/local/lib/node_modules','/usr/lib/node_modules']){
  if(fs.existsSync(root)) addModuleRoot(root);
}
// O runtime do Codex expõe um Node auxiliar com os módulos compartilhados. Esta dica
// é opcional e não afeta instalações normais do DSH.
if(process.env.CODEX_MCP_NODE_PATH){
  addModuleRoot(path.resolve(path.dirname(process.env.CODEX_MCP_NODE_PATH),'..','lib','node_modules'));
}

const URL = process.argv[2] || 'https://prezi.com/view/enykLwOvHQqnUQs3eNwo/';
const OUTDIR = process.argv[3] || process.env.PREZI_OUT || '/tmp/prezi2pdf/pages';
fs.mkdirSync(OUTDIR, { recursive:true });

const positiveInt=(name,fallback)=>{
  const value=Number.parseInt(process.env[name]||'',10);
  return Number.isFinite(value)&&value>0 ? value : fallback;
};
const W=1920, H=1080;
const MAX_PAGES=positiveInt('PREZI_MAX_PAGES',600);          // cap generoso de frames para frente
const SETTLE_POLL_MS=positiveInt('PREZI_SETTLE_POLL_MS',180); // intervalo de poll enquanto espera um frame estabilizar
const SETTLE_MAX=positiveInt('PREZI_SETTLE_MAX_MS',2600);     // janela máx por pressionamento
const NOCHANGE_STREAK_END=positiveInt('PREZI_NOCHANGE_STREAK',5); // frames idênticos consecutivos => terminal congelado
const DEADLINE_MS=positiveInt('PREZI_DEADLINE_MS',180000);    // cap duro limitado: ~3 min de navegação (~4.5 wall)

function loadPackage(name){
  try { return require(name); } catch {}
  for(const root of moduleRoots){
    try { return require(path.join(root,name)); } catch {}
  }
  throw new Error(`${name} não encontrado. Instale-o em node_modules ou defina PLAYWRIGHT_NODE_MODULES`);
}

const playwright = loadPackage('playwright');
if(!playwright?.chromium) throw new Error('Playwright chromium não disponível neste pacote');
let pngjs;
try { pngjs = loadPackage('pngjs'); } catch {}

function isBlank(buf){ // quadro todo-branco ou todo-preto
  // screenshot() devolve PNG comprimido, não um buffer RGBA. Sem pngjs, não
  // filtramos quadros em branco, mas a captura continua segura.
  if(!buf || !pngjs?.PNG) return false;
  try{
    const { data, width, height }=pngjs.PNG.sync.read(buf);
    const n=width*height; let white=0, black=0;
    for(let i=0;i<data.length;i+=4){
      const r=data[i], g=data[i+1], b=data[i+2];
      if(r>=250&&g>=250&&b>=250) white++;
      if(r<=5&&g<=5&&b<=5) black++;
    }
    return white>=n*0.9 || black>=n*0.9;
  }catch{return false;}
}
const hash=buf=>crypto.createHash('sha256').update(buf).digest('hex').slice(0,16);

async function main(){
  const launchOptions={ headless:true, args:['--no-sandbox','--disable-dev-shm-usage','--force-device-scale-factor=1'] };
  const chromiumCandidates=[
    process.env.PREZI_CHROMIUM_PATH,
    process.env.CHROMIUM_PATH,
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
  ].filter(Boolean);
  const systemChromium=chromiumCandidates.find(candidate=>fs.existsSync(candidate));
  if(systemChromium) launchOptions.executablePath=systemChromium;
  const browser=await playwright.chromium.launch(launchOptions);
  try{
    const page=await browser.newPage();
    await page.setViewportSize({ width:W, height:H });
    const snap=()=>page.screenshot({ type:'png', clip:{ x:0,y:0,width:W,height:H } });

    async function settle(){ // retorna primeiro quadro estável dentro da janela
      let prev=null, t0=Date.now();
      while(Date.now()-t0<SETTLE_MAX){
        const c=await snap();
        if(prev&&Buffer.compare(prev,c)===0) return c;
        prev=c;
        await page.waitForTimeout(SETTLE_POLL_MS);
      }
      return prev||null;
    }

    // --- Entrar no present mode ---
    await page.goto(URL,{ waitUntil:'domcontentloaded', timeout:60000 });
    await page.waitForTimeout(4000);
    for(const label of ['Reject All','Accept Cookies']){
      const cookieButton=page.getByRole('button',{ name:label, exact:true }).first();
      if(await cookieButton.count()===0) continue;
      try{ await cookieButton.click({ timeout:3000 }); await page.waitForTimeout(400); break; }catch{}
    }
    await page.locator('header').evaluateAll(elements=>elements.forEach(element=>{ element.style.display='none'; }));
    const presentSelectors=['.viewer-common-info-overlay-button-filled','button[aria-label="Present"]','.webgl-viewer-embed-center-container button','text=Present'];
    let clicked=false, presentFrame=null;
    for(const frame of page.frames()){
      if(clicked) break;
      for(const sel of presentSelectors){
        const candidate=frame.locator(sel).first();
        try{
          if(await candidate.count()===0) continue;
          await candidate.click({ timeout:3000 });
          clicked=true; presentFrame=frame; console.log('CLICK present via '+sel+' in '+frame.url()); break;
        }
        catch(e){ console.log('FAIL click '+sel+': '+e.message.slice(0,90)); }
      }
    }
    if(!clicked) throw new Error('Não encontrou o botão Present');
    try{ await page.locator('#onetrust-consent-sdk').evaluateAll(elements=>elements.forEach(element=>{ element.style.display='none'; })); }catch{}
    try{ await presentFrame.addStyleTag({ content:'.webgl-viewer-navbar,.webgl-viewer-navigation-button-next,.webgl-viewer-navigation-button-prev{display:none!important;opacity:0!important;pointer-events:none!important;}' }); }catch{}
    await page.mouse.move(0,0);
    await page.waitForTimeout(5000);

    // --- Capturar quadro inicial estável (F0) ---
    let f0=null, streak=0, fi=0; const tStart=Date.now();
    while(Date.now()-tStart<13000 && fi++<12){
      const s=await settle();
      if(!s||isBlank(s)) continue;
      if(f0&&Buffer.compare(f0,s)===0){ streak++; if(streak>=3) break; }
      else streak=0;
      f0=s;
    }
    if(!f0) throw new Error('Não foi possível capturar um quadro inicial não vazio');
    console.log('F0 hash '+hash(f0)+' bytes '+f0.length);
    const DEADLINE=Date.now()+DEADLINE_MS;

    // --- Navegação para frente: ArrowRight + capturar cada quadro distinto não-branco ---
    const pages=[{ index:0, data:f0 }];
    let last=f0, dupStreak=0;
    for(let p=1;p<MAX_PAGES && Date.now()<DEADLINE;p++){
      try{ await page.keyboard.press('ArrowRight'); }catch(e){ console.log('FAIL press '+p+': '+e.message.slice(0,80)); break; }
      const s=await settle();
      if(!s){ console.log(`  -> null@p${p}`); break; }
      const blank=isBlank(s);
      console.log(`p${p}: blank=${blank} hash=${hash(s)} dupStreak=${dupStreak}`);
      if(blank) continue;
      if(Buffer.compare(f0,s)===0){ console.log(`  -> f0@p${p}`); break; }
      if(Buffer.compare(last,s)===0){
        dupStreak++;
        if(dupStreak>=NOCHANGE_STREAK_END){ console.log(`END: frozen (no change x${dupStreak}) at frame ${p}`); break; }
        continue;
      }
      dupStreak=0; last=s; pages.push({ index:p, data:s });
    }

    // --- Escrever PNGs + manifest ---
    for(const pg of pages) fs.writeFileSync(`${OUTDIR}/${String(pg.index).padStart(3,'0')}.png`, pg.data);
    const manifest={ url:URL, presentMode:true, navigation:'ArrowRight', pages:pages.map(p=>({ index:p.index, file:`${String(p.index).padStart(3,'0')}.png`, size:Buffer.byteLength(p.data), hash:hash(p.data) })) };
    fs.writeFileSync(path.join(OUTDIR,'..','manifest.json'), JSON.stringify(manifest,null,2));

    console.log(`CAPTURED ${pages.length} pages -> ${OUTDIR}`);
  } finally {
    await browser.close();
  }
}

await main();
