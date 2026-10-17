const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const root = path.resolve(__dirname,'../..');
  const demo = JSON.parse(fs.readFileSync(path.join(root,'docs/stage9a_demo_selection.json'),'utf8'));
  const file = path.join(root,'docs/stage9a_verification.json');
  const report = JSON.parse(fs.readFileSync(file,'utf8'));
  const browser = await chromium.launch({headless:true});
  let replay;
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100}});
    await context.route('**://tile.openstreetmap.org/**',r=>r.abort());
    const page = await context.newPage();
    const errors=[]; let reads=0;
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.url().includes('/positions/latest'))reads++;});
    const unrelatedUrl='http://127.0.0.1:8000/routing/vehicles/S4_VAN_A/positions/latest';
    const unrelatedBefore=(await (await fetch(unrelatedUrl)).json()).position?.id ?? null;
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('button',{name:'Driver',exact:true}).click();
    await page.getByRole('button',{name:'Route',exact:true}).click();
    const panel=page.getByRole('region',{name:'Database driver route'});
    await panel.getByLabel('Driver test vehicle').selectOption(demo.vehicle_id);
    await panel.getByRole('button',{name:demo.direction==='morning'?'Morning Pickup':'Afternoon Drop-off',exact:true}).click();
    await panel.getByTestId('driver-trip-id').filter({hasText:demo.trip_id}).waitFor();
    await panel.getByText('Fixed trip itinerary and estimates',{exact:true}).click();
    replay=spawn(path.join(root,'backend/.venv/Scripts/python.exe'),[
      path.join(root,'backend/replay_positions.py'),'--vehicle-id',demo.vehicle_id,'--trip-id',demo.trip_id,
      '--fixture',path.join(root,'data/gps_replay_synthetic.csv'),'--speed','5','--rebase-to-now'],{cwd:root,windowsHide:true});
    let output='',stderr='';replay.stdout.on('data',b=>output+=b);replay.stderr.on('data',b=>stderr+=b);
    const done=new Promise((resolve,reject)=>{replay.on('error',reject);replay.on('exit',code=>code===0?resolve():reject(new Error(stderr)));});
    done.catch(()=>{});
    replay.stdin.end('\n');
    const marker=panel.locator('.saferide-position-marker').first();await marker.waitFor();
    await panel.getByRole('region',{name:'Vehicle GPS status'}).getByText('Vehicle position: fresh',{exact:true}).waitFor();
    const map=panel.locator('.leaflet-container').first();
    await map.locator('.leaflet-control-zoom-out').click();await page.waitForTimeout(400);
    const staticBefore=await map.locator('.saferide-map-marker').first().getAttribute('style');
    const movingBefore=await marker.getAttribute('style');
    await page.waitForTimeout(7000);
    const movingAfter=await marker.getAttribute('style');
    const staticAfter=await map.locator('.saferide-map-marker').first().getAttribute('style');
    assert.notEqual(movingAfter,movingBefore,'Backend position marker should move.');
    assert.equal(staticAfter,staticBefore,'Position update must preserve the user viewport.');
    await done;
    const latest=await (await fetch(`http://127.0.0.1:8000/routing/vehicles/${demo.vehicle_id}/positions/latest`)).json();
    assert.equal(latest.position.source,'simulation');assert.equal(latest.position.trip_id,demo.trip_id);
    assert.equal((await (await fetch(unrelatedUrl)).json()).position?.id ?? null,unrelatedBefore);
    await page.screenshot({path:path.join(root,'docs/stage9a-driver.png'),fullPage:true});
    await panel.getByRole('button',{name:'Back to driver dashboard',exact:true}).click();
    const readsBefore=reads;await page.waitForTimeout(2600);assert.equal(reads,readsBefore,'Unmount must stop position polling.');
    assert.deepEqual(errors,[]);
    report.browser={...demo,replay_samples:(output.match(/duplicate=False/g)||[]).length,
      source:'simulation',movement:'synthetic stop sequence, not a driven road trace',
      checks:['real replay script ingestion','backend marker moved','manual zoom preserved','unrelated vehicle unchanged','unmount stops polling'],page_errors:errors};
    fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.browser,null,2));
  } finally {if(replay && replay.exitCode===null)replay.kill();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
