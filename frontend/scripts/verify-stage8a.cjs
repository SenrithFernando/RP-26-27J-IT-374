// Real Admin POSTs + separate read-only Driver tab; failure cases are browser-only fixtures.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    await context.route('**://tile.openstreetmap.org/**', route => route.abort());
    const admin = await context.newPage();
    const driver = await context.newPage();
    const errors = [], driverWrites = [];
    let latestReads = 0;
    driver.on('pageerror', error => errors.push(error.message));
    driver.on('request', request => {
      if (request.url().includes('/api/') && request.method() !== 'GET') driverWrites.push(request.method()+' '+request.url());
      if (request.url().includes('/api/routes/latest?')) latestReads++;
    });
    await admin.goto('http://127.0.0.1:5173');
    await admin.getByRole('button', { name:'Administrator', exact:true }).click();
    await admin.getByRole('button', { name:'Routes', exact:true }).click();
    await admin.getByLabel('Route vehicle').selectOption('S4_VAN_A');
    await admin.getByText(/Current route ROUTE_/).waitFor();
    const today = new Intl.DateTimeFormat('en-CA', { timeZone:'Asia/Colombo', year:'numeric', month:'2-digit', day:'2-digit' }).format(new Date());
    async function generate(direction) {
      await admin.bringToFront();
      await admin.getByRole('button', { name:direction==='morning'?'Morning Pickup':'Afternoon Drop-off', exact:true }).click();
      await admin.getByText(/Current route ROUTE_/).waitFor();
      await admin.getByLabel('Duration provider').selectOption('simulation');
      await admin.getByLabel('Service date', { exact:true }).fill(today);
      const response = admin.waitForResponse(r => r.request().method()==='POST' && r.url().endsWith('/routes/generate'));
      await admin.getByRole('button', { name:'Generate route', exact:true }).click();
      const result = await (await response).json();
      assert.equal(result.feasibility_status,'feasible',JSON.stringify(result.errors));
      return result;
    }
    const first = await generate('morning');
    await driver.goto('http://127.0.0.1:5173');
    await driver.getByRole('button', { name:'Driver', exact:true }).click();
    await driver.getByRole('button', { name:'Route', exact:true }).click();
    const panel = driver.getByRole('region', { name:'Database driver route' });
    await panel.getByLabel('Driver test vehicle').selectOption('S4_VAN_A');
    async function matches(route) {
      await panel.getByTestId('driver-route-id').filter({hasText:route.route_id}).waitFor({timeout:22000});
      assert((await panel.getByTestId('driver-route-version').innerText()).includes(`Version: ${route.version} ·`));
      const ids = await panel.getByRole('list', {name:'Driver stored actions'}).locator('> li').evaluateAll(nodes=>nodes.map(n=>n.dataset.eventId));
      assert.deepEqual(ids,route.stops.map(s=>s.event_id));
      await panel.getByText('Current stored pre-trip plan', {exact:true}).waitFor();
      await panel.getByText('Stop sequence — not a road route', {exact:true}).waitFor();
    }
    await driver.bringToFront();
    await matches(first);
    await panel.getByText('School: Stage 4 synthetic school A · S4_SCHOOL_A', {exact:true}).first().waitFor();
    const second = await generate('morning');
    assert(second.version > first.version);
    await driver.bringToFront();
    await matches(second); // Actual visibility refresh or 15-second poll; no button click.
    const afternoon = await generate('afternoon');
    await driver.bringToFront();
    await panel.getByRole('button', {name:'Afternoon Drop-off',exact:true}).click();
    await matches(afternoon);
    await panel.getByRole('button', {name:'Refresh route',exact:true}).click();
    await matches(afternoon);

    // Each mock below is a UI failure fixture, not a new backend optimization result.
    const latestPattern = '**/api/routes/latest?**';
    const planPattern = '**/api/routing/plans/S4_VAN_A/**';
    await driver.route(latestPattern, r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Stage 8A backend error fixture'})}));
    await panel.getByRole('button', {name:'Refresh route',exact:true}).click();
    await panel.getByText(/Stage 8A backend error fixture/).waitFor();
    assert.equal(await panel.getByRole('list',{name:'Driver stored actions'}).count(),0);
    await driver.unroute(latestPattern);
    await driver.route(latestPattern,r=>r.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No stored route fixture'})}));
    await panel.getByRole('button',{name:'Refresh route',exact:true}).click();
    await panel.getByText(/No stored afternoon route for S4_VAN_A/).waitFor();
    await driver.unroute(latestPattern);
    const actualPlan = await (await driver.request.get('http://127.0.0.1:8000/routing/plans/S4_VAN_A/afternoon')).json();
    await driver.route(planPattern,r=>r.fulfill({contentType:'application/json',body:JSON.stringify({...actualPlan,is_current:false,generation_status:'stale',errors:['Stage 8A stale fixture']})}));
    await panel.getByRole('button',{name:'Refresh route',exact:true}).click();
    await panel.getByText('Stage 8A stale fixture',{exact:true}).waitFor();
    assert.equal(await panel.getByRole('list',{name:'Driver stored actions'}).count(),0);
    await driver.unroute(planPattern);
    const invalid = {...afternoon,feasibility_status:'infeasible',is_current:false,planning_status:'infeasible',errors:['Stage 8A infeasible fixture'],stops:[]};
    await driver.route(latestPattern,r=>r.fulfill({contentType:'application/json',body:JSON.stringify(invalid)}));
    await panel.getByRole('button',{name:'Refresh route',exact:true}).click();
    await panel.getByText('Stage 8A infeasible fixture',{exact:true}).waitFor();
    assert.equal(await panel.getByRole('list',{name:'Driver stored actions'}).count(),0);
    await driver.unroute(latestPattern);
    await driver.route(latestPattern,r=>r.fulfill({contentType:'application/json',body:JSON.stringify({...afternoon,service_date:'2000-01-01'})}));
    await panel.getByRole('button',{name:'Refresh route',exact:true}).click();
    await panel.getByText('Freshness: Past service date — historical plan',{exact:true}).waitFor();
    assert.equal(await panel.getByRole('list',{name:'Driver stored actions'}).count(),0);
    await driver.unroute(latestPattern);

    // A delayed obsolete morning response cannot overwrite a newer afternoon selection.
    let release, started = false;
    const held = new Promise(resolve=>{release=resolve;});
    await driver.route(latestPattern,async r=>{
      if(r.request().url().includes('direction=morning')) {started=true;await held;try{await r.fulfill({contentType:'application/json',body:JSON.stringify(first)});}catch{}}
      else await r.continue();
    });
    await panel.getByRole('button',{name:'Morning Pickup',exact:true}).click();
    await driver.waitForFunction(()=>true);
    for(let i=0;i<30&&!started;i++) await driver.waitForTimeout(50);
    assert(started);
    await panel.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();
    await matches(afternoon); release();
    await driver.waitForTimeout(150);
    await matches(afternoon); await driver.unroute(latestPattern);

    // Use a controllable browser clock only for timer/visibility cleanup checks.
    await driver.clock.install();
    await driver.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'));});
    const hiddenCount=latestReads;
    await driver.clock.fastForward(45000);
    assert.equal(latestReads,hiddenCount,'Hidden page must not poll');
    const resumed=driver.waitForRequest(r=>r.url().includes('/api/routes/latest?'));
    await driver.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'));});
    await resumed; await matches(afternoon);
    const polled=driver.waitForRequest(r=>r.url().includes('/api/routes/latest?'));
    await driver.clock.fastForward(15000); await polled; await matches(afternoon);
    await driver.screenshot({path:path.resolve(__dirname,'../../docs/stage8a-driver.png'),fullPage:true});
    await panel.getByRole('button',{name:'Back to driver dashboard',exact:true}).click();
    const unmountedCount=latestReads;
    await driver.clock.fastForward(45000);
    assert.equal(latestReads,unmountedCount,'Closing route view must clean up polling');
    assert.deepEqual(driverWrites,[]); assert.deepEqual(errors,[]);
    const final = await (await driver.request.get('http://127.0.0.1:8000/routes/latest?vehicle_id=S4_VAN_A&direction=morning')).json();
    assert.equal(final.route_id,second.route_id,'Driver reads must not create versions');
    const report = {recorded_at:new Date().toISOString(),vehicle_id:'S4_VAN_A',
      first_morning:{route_id:first.route_id,version:first.version}, regenerated_morning:{route_id:second.route_id,version:second.version},
      afternoon:{route_id:afternoon.route_id,version:afternoon.version},actions_per_direction:afternoon.stops.length,
      driver_write_requests:driverWrites,browser_errors:errors,
      checks:['Real separate-tab Admin generation and Driver latest-version/stops match','Morning regeneration received without Driver generation',
        'Independent afternoon selection','Manual read-only refresh','503/404/stale/infeasible/past-date UI fixtures',
        'Obsolete request ignored','Hidden polling paused','Visible polling resumed','Unmount polling cleanup'],
      source:'Actual local Admin/Driver integration; error states explicitly injected as browser-only fixtures. No Google API calls.'};
    fs.writeFileSync(path.resolve(__dirname,'../../docs/stage8a_verification.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
