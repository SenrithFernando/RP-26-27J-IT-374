// Requires the local backend, Vite, and Playwright (development verification only).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*.tile.openstreetmap.org/**', route => route.abort());
  let created;
  try {
    const students = await (await page.request.get('http://127.0.0.1:8000/routing/students')).json();
    const example = students.find(s => s.id === 'S4_STUDENT_01');
    assert(example, 'Run seed_routing_demo.py first');
    await page.goto('http://localhost:5173');
    await page.getByRole('button', { name: 'Administrator', exact: true }).click();
    await page.getByRole('button', { name: 'Students', exact: true }).click();
    await page.getByRole('button', { name: 'Add Student', exact: true }).click();
    const dialog = page.getByRole('dialog');
    const name = `Stage 5 browser synthetic ${Date.now()}`;
    await dialog.getByLabel('Name', { exact: true }).fill(name);
    await dialog.getByLabel('School', { exact: true }).selectOption(example.school_id);
    await dialog.getByLabel('Vehicle', { exact: true }).selectOption(example.vehicle_id);
    await dialog.getByLabel('Address', { exact: true }).fill('Synthetic distant home for infeasibility verification');
    await dialog.getByLabel('Home latitude', { exact: true }).fill('80');
    await dialog.getByLabel('Home longitude', { exact: true }).fill('-170');
    await dialog.getByRole('checkbox').check();
    const save = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/routing/students'));
    await dialog.getByRole('button', { name: 'Save student', exact: true }).click();
    created = await (await save).json();
    assert.equal(created.save_status, 'saved');
    assert.equal(created.routing.outcome, 'failed');
    await page.getByText('Student saved; routing failed', { exact: true }).waitFor();
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    await page.getByRole('button', { name: 'Routes', exact: true }).click();
    await page.getByLabel('Route vehicle').selectOption(example.vehicle_id);
    await page.getByText('No older itinerary is displayed as current.').waitFor();
    assert.equal(await page.getByText(/Current route ROUTE_/).count(), 0);
    await page.getByRole('button', { name: 'Students', exact: true }).click();
    await page.getByLabel('Search students').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await row.getByRole('button', { name: 'Edit', exact: true }).click();
    await dialog.getByLabel('Address', { exact: true }).fill('Synthetic corrected home matching confirmed fixture coordinates');
    await dialog.getByLabel('Home latitude', { exact: true }).fill(String(example.home_latitude));
    await dialog.getByLabel('Home longitude', { exact: true }).fill(String(example.home_longitude));
    await dialog.getByRole('checkbox').check();
    // A rejected write must stay in the form, distinct from a saved routing failure.
    const writeUrl = `**/api/routing/students/${created.id}`;
    await page.route(writeUrl, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic save failure' }) }));
    await dialog.getByRole('button', { name: 'Save student', exact: true }).click();
    await dialog.getByText('Student save failed: Synthetic save failure', { exact: true }).waitFor();
    assert(await dialog.isVisible());
    await page.unroute(writeUrl);
    const correctedResponse = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith(`/routing/students/${created.id}`));
    await dialog.getByRole('button', { name: 'Save student', exact: true }).click();
    const corrected = await (await correctedResponse).json();
    assert.equal(corrected.routing.outcome, 'success', JSON.stringify(corrected.routing));
    await page.getByText('Student saved; pre-trip routes refreshed', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Routes', exact: true }).click();
    await page.getByLabel('Route vehicle').selectOption(example.vehicle_id);
    await page.getByText(/Current route ROUTE_/).waitFor();
    await page.getByRole('button', { name: 'Afternoon Drop-off', exact: true }).click();
    await page.getByText(/Current route ROUTE_/).waitFor();
    await page.getByRole('button', { name: 'Students', exact: true }).click();
    await page.getByLabel('Search students').fill(name);
    await page.getByRole('row').filter({ hasText: name }).getByRole('button', { name: 'Deactivate', exact: true }).click();
    const deactivatedResponse = page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(`/routing/students/${created.id}/status`));
    await dialog.getByRole('button', { name: 'Deactivate student', exact: true }).click();
    const deactivated = await (await deactivatedResponse).json();
    assert.equal(deactivated.active, false);
    assert.equal(deactivated.routing.outcome, 'success');
    assert.deepEqual(errors, [], 'Browser runtime errors');
    console.log(JSON.stringify({ student_id: created.id, saved_infeasible: created.routing.event_id,
      corrected: corrected.routing.plans, deactivated: deactivated.routing.event_id, browser_errors: errors }, null, 2));
  } finally {
    if (created?.id) await page.request.patch(`http://127.0.0.1:8000/routing/students/${created.id}/status`, { data: { active: false } });
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
