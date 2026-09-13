
const { chromium } = require('playwright');
(async () => {
  try {
    const b = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const pg = await b.newPage();
    await pg.goto('about:blank', { timeout: 15000 });
    console.log('CHROMIUM_OK version=' + await b.version());
    await b.close();
  } catch (e) {
    console.log('CHROMIUM_ERR:', e.message);
  }
})();
