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
    await page.goto('http://localhost:5173');
    await page.getByRole('button', { name: 'Administrator', exact: true }).click();
    await page.getByRole('button', { name: 'Routes', exact: true }).click();
    await page.getByLabel('Route vehicle').selectOption('S4_VAN_A');
    await page.getByRole('button', { name: 'Morning Pickup', exact: true }).click();
    await page.getByText(/ML available: synthetic-xgb-v1-/).waitFor();
    const provider = page.getByLabel('Duration provider');
    async function generate() {
      const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/routes/generate'));
      await page.getByRole('button', { name: 'Generate route', exact: true }).click();
      const result = await (await response).json();
      await page.getByText(new RegExp(`version ${result.version}\\.`)).first().waitFor();
      return result;
    }
    await provider.selectOption('unavailable');
    const unavailable = await generate();
    assert.equal(unavailable.feasibility_status, 'unavailable');
    assert.equal(unavailable.driving_seconds, null);
    await page.getByText('No older itinerary is displayed as current.').waitFor();
    assert.equal(await page.getByText(/Current route ROUTE_/).count(), 0);
    await provider.selectOption('simulation');
    await page.getByLabel('Traffic scenario').selectOption('northbound_delay');
    const simulated = await generate();
    assert.equal(simulated.provider_source.traffic_scenario, 'northbound_delay');
    assert(simulated.provider_source.scenario_modified_directed_arcs > 0);
    await provider.selectOption('google');
    await page.getByLabel('Fallback policy').selectOption('ml');
    await page.getByRole('checkbox', { name: /Force live adapter failure/ }).check();
    const fallback = await generate();
    assert.equal(fallback.feasibility_status, 'feasible');
    assert.equal(fallback.provider_source.duration_source, 'ml_prediction');
    assert(fallback.provider_source.route_fallback_reasons.some(reason => reason.includes('forced')));
    await page.getByText('ML-predicted driving (synthetic training)', { exact: true }).waitFor();
    await page.getByText(/Fallback reason: Local demonstration forced/).first().waitFor();
    const status = await (await page.request.get('http://127.0.0.1:8000/traffic/status')).json();
    if (!status.google.configured) await page.getByText(/Google Routes API not configured:/).waitFor();
    await page.getByText('Alternatives under the same snapshot', { exact: true }).waitFor();
    await page.getByText('Stop sequence — not a road route', { exact: true }).waitFor();
    const stored = await (await page.request.get('http://127.0.0.1:8000/routes/latest?vehicle_id=S4_VAN_A&direction=morning')).json();
    assert.equal(stored.route_id, fallback.route_id);
    assert.deepEqual(errors, []);
    await page.keyboard.press('Control+Home');
    await page.screenshot({ path: path.resolve(__dirname, '../../docs/stage7-routes.png'), fullPage: true });
    console.log(JSON.stringify({ unavailable_version: unavailable.version, scenario_version: simulated.version,
      forced_failure_version: fallback.version, selected_source: fallback.provider_source.duration_source,
      model_version: fallback.provider_source.model_version, live_configured: status.google.configured,
      fallback_reason: fallback.provider_source.route_fallback_reasons, driving_seconds: fallback.driving_seconds,
      browser_errors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
