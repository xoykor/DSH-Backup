
async function main(){
  const { chromium } = await import('playwright');
  try {
    const b = await chromium.launch({ args:['--no-sandbox','--disable-dev-shm-usage'] });
    console.log('ESM_CHROMIUM_OK', await b.version());
    await b.close();
  } catch(e){ console.log('ESM_CHROMIUM_ERR:', e.message); }
}
main().catch(e=>console.log('MAIN_ERR', e.message));
