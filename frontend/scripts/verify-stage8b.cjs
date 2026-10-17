// Real PostgreSQL lifecycle via Driver UI; uses isolated fixtures from test_trip_lifecycle.py.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const file = path.resolve(__dirname, '../../docs/stage8b_verification.json');
  const report = JSON.parse(fs.readFileSync(file,'utf8'));
  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100}});
    await context.route('**://tile.openstreetmap.org/**', r => r.abort());
    const page = await context.newPage();
    const errors = [], mutations = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (r.url().includes('/api/') && r.method()!=='GET') mutations.push(r.method()+' '+new URL(r.url()).pathname); });
    async function open() {
      await page.goto('http://127.0.0.1:5173');
      await page.getByRole('button',{name:'Driver',exact:true}).click();
      await page.getByRole('button',{name:'Route',exact:true}).click();
      const panel = page.getByRole('region',{name:'Database driver route'});
      await panel.getByLabel('Driver test vehicle').selectOption(report.vehicle_id);
      await panel.getByRole('button',{name:report.direction==='morning'?'Morning Pickup':'Afternoon Drop-off',exact:true}).click();
      return panel;
    }
    let panel = await open();
    await panel.getByRole('button',{name:'Create planned trip (manual prototype)',exact:true}).click();
    await panel.getByTestId('driver-trip-state').filter({hasText:'PLANNED'}).waitFor();
    const tripId = (await panel.getByTestId('driver-trip-id').innerText()).replace('Trip ID: ','');
    await panel.getByRole('button',{name:'Start trip (manual prototype)',exact:true}).click();
    await panel.getByTestId('driver-trip-state').filter({hasText:'ACTIVE'}).waitFor();
    assert((await panel.getByTestId('driver-trip-route').innerText()).includes(report.route_id));
    assert.equal(await panel.getByRole('list',{name:'Fixed trip actions'}).locator('> li').count(),4);
    assert.equal(await panel.getByRole('list',{name:'Unfinished trip actions'}).locator('> li').count(),2);
    // Different planning direction must never replace the active trip's fixed route.
    await panel.getByRole('button',{name:report.direction==='morning'?'Afternoon Drop-off':'Morning Pickup',exact:true}).click();
    await panel.getByTestId('driver-trip-state').filter({hasText:'ACTIVE'}).waitFor();
    assert((await panel.getByTestId('driver-trip-id').innerText()).includes(tripId));
    // Fresh page load re-reads PostgreSQL; no lifecycle mutation is triggered by reload.
    const writesBeforeReload = mutations.length;
    panel = await open();
    await panel.getByTestId('driver-trip-state').filter({hasText:'ACTIVE'}).waitFor();
    assert((await panel.getByTestId('driver-trip-id').innerText()).includes(tripId));
    assert.equal(mutations.length,writesBeforeReload);
    await panel.getByText(/Sri Lanka/).first().waitFor();
    await page.screenshot({path:path.resolve(__dirname,'../../docs/stage8b-driver.png'),fullPage:true});
    await panel.getByRole('button',{name:'End trip (manual prototype)',exact:true}).click();
    await panel.getByText(/Ending does not mark students delivered/).waitFor();
    await panel.getByRole('button',{name:'Confirm end trip',exact:true}).click();
    await panel.getByTestId('driver-trip-state').filter({hasText:'COMPLETED'}).waitFor();
    assert.equal(await panel.getByRole('list',{name:'Unfinished trip actions'}).locator('> li').count(),2);
    assert.deepEqual(errors,[]);
    report.browser={trip_id:tripId,route_id:report.route_id,final_state:'COMPLETED',unfinished_actions:2,
      checks:['create/start/end in Driver','reload retains active trip','direction change retains active snapshot','Sri Lankan times displayed','end confirmation does not claim delivery'],mutations,page_errors:errors};
    fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report.browser,null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
