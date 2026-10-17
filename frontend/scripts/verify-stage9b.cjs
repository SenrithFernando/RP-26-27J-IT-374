// Real active-trip current-stop arrival through the API and Driver UI; no paid APIs.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const file=path.resolve(__dirname,'../../docs/stage9b_verification.json');
  const report=JSON.parse(fs.readFileSync(file,'utf8'));
  const base='http://127.0.0.1:8000';
  const browser=await chromium.launch({headless:true});
  async function api(url,body) {
    const res=await fetch(base+url,body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
    const result=await res.json();assert(res.ok,JSON.stringify(result));return result;
  }
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1100}});
    await context.route('**://tile.openstreetmap.org/**',r=>r.abort());
    const page=await context.newPage();const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('button',{name:'Driver',exact:true}).click();await page.getByRole('button',{name:'Route',exact:true}).click();
    const panel=page.getByRole('region',{name:'Database driver route'});
    await panel.getByLabel('Driver test vehicle').selectOption(report.vehicle_id);
    const arrival=panel.getByRole('region',{name:'Current stop arrival'});
    await arrival.getByTestId('arrival-state').filter({hasText:'GPS unknown'}).waitFor();
    const original=await api(`/trips/${report.trip_id}`);
    const current=await api(`/trips/${report.trip_id}/arrival`);
    const stop=current.current_stop;
    const run=Date.now();let index=0;
    async function sample(offset=0) {
      const body={sample_id:`9b-browser-${run}-${index++}`,trip_id:report.trip_id,source:'simulation',
        latitude:stop.latitude+offset/111194.9266,longitude:stop.longitude,recorded_at:new Date().toISOString()};
      const result=await api(`/routing/vehicles/${report.vehicle_id}/positions`,body);return {body,result};
    }
    await sample(100);await arrival.getByTestId('arrival-state').filter({hasText:'Approaching'}).waitFor();
    const first=await sample();await arrival.getByTestId('arrival-state').filter({hasText:'Arrival candidate'}).waitFor();
    const started=Date.now();
    await page.waitForTimeout(5000);await sample(60);
    await page.waitForTimeout(5000);await sample(49);
    await page.waitForTimeout(Math.max(0,16000-(Date.now()-started)));const final=await sample();
    await arrival.getByTestId('arrival-state').filter({hasText:'Arrived',exact:true}).waitFor();
    const event=(await api(`/trips/${report.trip_id}/arrival`)).arrival_event;
    const repeated=await api(`/routing/vehicles/${report.vehicle_id}/positions`,final.body);
    assert.equal(repeated.duplicate,true);
    await sample(100);
    assert.deepEqual((await api(`/trips/${report.trip_id}/arrival`)).arrival_event,event);
    assert.deepEqual((await api(`/trips/${report.trip_id}`)).unfinished_actions,original.unfinished_actions);
    await arrival.screenshot({path:path.resolve(__dirname,'../../docs/stage9b-arrival.png')});
    await arrival.getByRole('button',{name:'Next stop (manual; no passenger confirmation)',exact:true}).click();
    await arrival.getByTestId('arrival-state').filter({hasText:'GPS unknown'}).waitFor();
    const advanced=await api(`/trips/${report.trip_id}/arrival`);
    assert(advanced.current_stop.sequence>stop.sequence);assert.equal(advanced.arrival_event,null);
    report.browser={trip_id:report.trip_id,stop_sequence:stop.sequence,event_id:event.event_id,arrived_at:event.arrived_at,
      source:event.source,first_inside_at:first.body.recorded_at,next_stop_sequence:advanced.current_stop.sequence,
      checks:['GPS unknown -> approaching -> candidate -> arrived','real repeated recorded-time observations',
        'duplicate arrival unchanged','passenger actions unchanged','manual next stop starts GPS unknown, including colocated stop'],page_errors:errors};
    assert.deepEqual(errors,[]);fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.browser,null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
