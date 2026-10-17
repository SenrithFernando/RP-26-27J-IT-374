// Real normal-backend worker and Driver actions. Only isolated S9C test records are changed.
const { chromium } = require('playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
  const file=path.resolve(__dirname,'../../docs/stage9c_verification.json');const report=JSON.parse(fs.readFileSync(file,'utf8'));
  const base='http://127.0.0.1:8000';
  async function api(url,body){const r=await fetch(base+url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();assert(r.ok,JSON.stringify(value));return value;}
  assert(report.vehicle_id.startsWith('S9C_'),'Only synthetic Stage 9C vehicles are permitted.');
  const old=await api(`/trips/current?vehicle_id=${report.vehicle_id}`);
  if(old.trip && ['ACTIVE','PLANNED'].includes(old.trip.state))await api(`/trips/${old.trip.trip_id}/cancel`,{reason:'Synthetic browser verification: preserve prior fixture history, prepare a new route version.'});
  const route=await api('/routes/generate',{...old.trip.route.request_settings,include_geometry:false,provider:'simulation'});
  const browser=await chromium.launch({headless:true});const errors=[];
  async function open(){const ctx=await browser.newContext({viewport:{width:1440,height:1100}});await ctx.route('**://tile.openstreetmap.org/**',r=>r.abort());const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:5173');await page.getByRole('button',{name:'Driver',exact:true}).click();await page.getByRole('button',{name:'Route',exact:true}).click();const panel=page.getByRole('region',{name:'Database driver route'});await panel.getByLabel('Driver test vehicle').selectOption(report.vehicle_id);await panel.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();return {ctx,page,panel};}
  try{
    let {ctx,page,panel}=await open();
    await panel.getByLabel('Pickup window mode').selectOption('simulation_demo');await panel.getByLabel('Pickup window scope').selectOption('per_school');
    const created=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/trips'));
    await panel.getByRole('button',{name:'Create planned trip (manual prototype)',exact:true}).click();const trip=await(await created).json();
    await panel.getByRole('button',{name:'Start trip (manual prototype)',exact:true}).click();await panel.getByTestId('driver-trip-state').filter({hasText:'ACTIVE'}).waitFor();
    const arrival=await api(`/trips/${trip.trip_id}/arrival`);const stop=arrival.current_stop;const run=Date.now();
    const start=Date.now();let index=0;
    // Fresh repeated observations, actual wall-clock dwell, simulation source only.
    for(const offset of [0,5000,10000,16000]){
      await page.waitForTimeout(Math.max(0,start+offset-Date.now()));
      await api(`/routing/vehicles/${report.vehicle_id}/positions`,{sample_id:`9c-browser-${run}-${index++}`,trip_id:trip.trip_id,source:'simulation',latitude:stop.latitude,longitude:stop.longitude,recorded_at:new Date().toISOString()});
    }
    const pickup=panel.getByRole('region',{name:'Persistent pickup windows'});
    await pickup.getByText(/SIMULATION DEMO.*WAITING/).waitFor();
    const windows=await api(`/trips/${trip.trip_id}/pickup-windows`);assert.equal(windows.windows.length,1);const window=windows.windows[0];assert.equal(window.outcomes.length,3);
    const first=pickup.locator(`[data-student-id="${window.outcomes[0].student_id}"]`);const second=pickup.locator(`[data-student-id="${window.outcomes[1].student_id}"]`);
    // API failure must stay visible and must not mark the student picked up.
    const confirmPattern=`**/api/trips/${trip.trip_id}/pickups/${window.outcomes[0].student_id}/confirm`;
    await page.route(confirmPattern,r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Stage 9C save-error fixture'})}));
    await first.getByRole('button',{name:'Confirm pickup (manual prototype)',exact:true}).click();await pickup.getByText(/Stage 9C save-error fixture/).waitFor();await page.unroute(confirmPattern);
    await first.getByRole('button',{name:'Confirm pickup (manual prototype)',exact:true}).click();await first.getByTestId('pickup-outcome').filter({hasText:'PICKED_UP'}).waitFor();
    await second.getByRole('button',{name:'Cancel pickup',exact:true}).click();await second.getByLabel('Pickup cancellation reason').fill('Synthetic manual cancellation');await second.getByRole('button',{name:'Confirm pickup cancellation',exact:true}).click();await second.getByTestId('pickup-outcome').filter({hasText:'CANCELLED'}).waitFor();
    await ctx.close(); // No browser remains open while the worker expires the third student.
    const remaining=new Date(window.deadline_at).getTime()-Date.now();await new Promise(resolve=>setTimeout(resolve,Math.max(0,remaining)+1500));
    const expired=await api(`/trips/${trip.trip_id}/pickup-windows`);assert.equal(expired.windows[0].deadline_at,window.deadline_at);assert.deepEqual(expired.windows[0].outcomes.map(o=>o.state),['PICKED_UP','CANCELLED','MISSED']);
    ({ctx,page,panel}=await open());const restored=panel.getByRole('region',{name:'Persistent pickup windows'});await restored.getByTestId('pickup-outcome').filter({hasText:'MISSED'}).waitFor();
    assert(await restored.getByRole('button',{name:'Confirm pickup (manual prototype)',exact:true}).first().isDisabled());
    await restored.screenshot({path:path.resolve(__dirname,'../../docs/stage9c-pickups.png')});
    const history=await api(`/trips/${trip.trip_id}/pickup-history`);const historyStates=new Set(history.events.map(e=>e.to_state));for(const s of ['SCHEDULED','ARRIVED','WAITING','PICKED_UP','MISSED','CANCELLED'])assert(historyStates.has(s));
    const result=await api(`/trips/${trip.trip_id}`);assert.equal(result.unfinished_actions.filter(a=>a.action==='delivery'&&a.status==='PENDING').length,3);
    assert.deepEqual(errors,[]);report.browser={trip_id:trip.trip_id,vehicle_id:trip.vehicle_id,route_id:route.route_id,mode:'simulation_demo',duration_seconds:window.duration_seconds,
      deadline_at:window.deadline_at,outcomes:expired.windows[0].outcomes.map(o=>o.state),checks:['explicit demo/scope selection','real GPS arrival opens one shared window','visible API save error and retry',
        'manual pickup/cancel actions','browser closed during worker expiry','reconnect retains deadline and outcomes','invalid confirmation disabled','deliveries stay pending','all six states in ordered history'],page_errors:errors};
    fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.browser,null,2));await ctx.close();
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
