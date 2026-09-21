// Screenshot .diagram at 2x device scale for print-quality PNG embedding
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1020, height: 400 },
    deviceScaleFactor: 2,
  });
  await page.goto('file:///home/z/my-project/scripts/recon_report/diagram.html');
  await page.waitForTimeout(500);
  const el = await page.$('.diagram');
  await el.screenshot({ path: '/home/z/my-project/scripts/recon_report/diagram.png' });
  await browser.close();
  console.log('diagram.png written');
})();
