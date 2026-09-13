
async function main(){
  const { chromium } = await import('playwright');
  try {
    const b = await chromium.launch({ args:['--no-sandbox','--disable-dev-shm-usage'] });
    console.log('ESM_LAUNCHED', await b.version());
    const pg = await b.newPage();
    await pg.goto('about:blank',{timeout:15000});
    await new Promise(r=>setTimeout(r,5000)); // hold to expose residual hang
    console.log('ESM_HOLD_OK');
    await b.close();
  } catch(e){ console.log('ESM_ERR:', e.message); }
}
main().catch(e=>console.log('MAIN_ERR', e.message));
