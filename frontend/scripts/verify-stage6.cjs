const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*.tile.openstreetmap.org/**', route => route.abort());
    const stored = {};
    for (const direction of ['morning', 'afternoon']) {
      stored[direction] = await (await page.request.get(`http://127.0.0.1:8000/routes/latest?vehicle_id=S4_VAN_A&direction=${direction}`)).json();
      assert.equal(stored[direction].provider_source.duration_source, 'ml_prediction', 'Run ml.verify_pipeline first');
    }
    await page.goto('http://localhost:5173');
    await page.getByRole('button', { name: 'Administrator', exact: true }).click();
    await page.getByRole('button', { name: 'Routes', exact: true }).click();
    await page.getByLabel('Route vehicle').selectOption('S4_VAN_A');
    for (const direction of ['morning', 'afternoon']) {
      await page.getByRole('button', { name: direction === 'morning' ? 'Morning Pickup' : 'Afternoon Drop-off', exact: true }).click();
      await page.getByText(`Current route ${stored[direction].route_id} · version ${stored[direction].version}`, { exact: true }).waitFor();
      await page.getByText('ML-predicted driving (synthetic training)', { exact: true }).waitFor();
      await page.getByText(`${stored[direction].driving_seconds} s`, { exact: true }).waitFor();
      await page.getByText(/ML available: synthetic-xgb-v1-/).waitFor();
      assert.equal(await page.getByLabel('Duration provider').inputValue(), 'ml');
      assert.equal(await page.getByLabel('Weather planning input').inputValue(), '');
      const latest = await (await page.request.get(`http://127.0.0.1:8000/routes/latest?vehicle_id=S4_VAN_A&direction=${direction}`)).json();
      assert.equal(latest.route_id, stored[direction].route_id, 'Browser reads must not generate route versions');
    }
    await page.screenshot({ path: path.resolve(__dirname, '../../docs/stage6-routes.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ morning_version: stored.morning.version, afternoon_version: stored.afternoon.version,
      model_version: stored.morning.provider_source.model_version, browser_errors: errors, read_only_versions_preserved: true }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
