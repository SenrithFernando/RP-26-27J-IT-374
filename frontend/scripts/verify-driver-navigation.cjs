// Intercepted synthetic mobile contracts; external URLs never reach Google.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844}});
  await context.addInitScript(()=>{sessionStorage.setItem('saferide.login','synthetic-navigation-ui-only');Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>window.__copiedNavigation=value},configurable:true});});
  let sequence=1,arrived=false,confirmed=true,invalid=false,mismatch=false,fail=false,completed=false;
  const writes=[],external=[];
  const stops=[1,2,3].map((n)=>({sequence:n,event_id:`STOP_${n}`,location_id:`L${n}`,name:n===3?'Synthetic depot':`Synthetic landmark ${n}`,
   action:n===3?'end':'pickup',latitude:n===1?6.9:n===2?-6.91:0,longitude:n===1?79.9:n===2?79.91:0,
   location_confirmed:true,student_ids:[],student_names:{},school_id:null,service_seconds:0,waiting_seconds:0,driving_seconds_from_previous:0,
   load_before:0,load_after:0,input_source:'simulated',location_method:'manual',eta:'2026-10-19T15:00:00+05:30',arrival:'2026-10-19T15:00:00+05:30'}));
  function route(){return {route_id:'SAVED_NAV',version:28,vehicle_id:'UI_NAV_V',direction:'afternoon',service_date:'2026-10-19',departure:'2026-10-19T15:00:00+05:30',generated_at:'2026-10-19T14:00:00+05:30',
   request_settings:{provider:'simulation'},stops:stops.map(s=>({...s,location_confirmed:confirmed,latitude:invalid?100:s.latitude})),provider_source:{duration_source:'simulation'},feasibility_status:'feasible',is_current:false,execution_status:'active',roster_version:1,errors:[],planning_errors:[]};}
  function arrival(){return {trip_id:'UI_NAV_T',route_id:mismatch?'OTHER_ROUTE':'SAVED_NAV',state:arrived?'arrived':'approaching',gps_status:'fresh',
   current_stop:{...route().stops[sequence-1]},settings:{radius_metres:50,exit_radius_metres:75,dwell_seconds:15,min_observations:3,max_gap_seconds:10,freshness_seconds:20},
   arrival_event:arrived?{event_id:'SYNTHETIC_ARRIVAL',arrived_at:'2026-10-19T15:01:00+05:30',source:'simulation'}:null,can_advance:arrived&&sequence<3,observation_count:3};}
  await context.route('**/*',r=>{
   const u=new URL(r.request().url()),p=u.pathname;const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
   if(!['127.0.0.1','localhost'].includes(u.hostname)){external.push(u);return r.fulfill({body:'External navigation intercepted; no provider request.'});}
   if(!p.startsWith('/api/'))return r.continue();
   if(p==='/api/auth/me')return send({id:'UI_DRIVER',username:'synthetic.navigation',role:'driver',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:['UI_NAV_V'],student_ids:[]});
   if(p==='/api/routing/vehicles')return send([{id:'UI_NAV_V',capacity:20,input_source:'simulated'}]);
   if(p==='/api/routes/published')return send({published_route:null,publication_status:'published',trip:{trip_id:'UI_NAV_T',vehicle_id:'UI_NAV_V',direction:'afternoon',state:completed?'COMPLETED':'ACTIVE',route_id:'SAVED_NAV',route_version:28,route:route(),unfinished_actions:[],unfinished_action_count:0}});
   if(p==='/api/trips/UI_NAV_T/arrival')return fail?send({detail:'Controlled arrival unavailable'},503):send(arrival());
   if(p==='/api/trips/UI_NAV_T/advance-stop'){
    writes.push({method:r.request().method(),sequence:u.searchParams.get('expected_stop_sequence')});
    assert.equal(r.request().method(),'POST');assert.ok(arrived&&sequence<3);sequence++;arrived=false;return send(arrival());
   }
   if(r.request().method()!=='GET')writes.push({unexpected:p});
   if(p.endsWith('/positions/latest'))return send({position:null,status:'unknown',age_seconds:null});
   if(p==='/api/auth/tracking')return send([]);
   if(p==='/api/pickup-policy')return send({morning_scope:'per_stop',afternoon_scope:'per_school',demo_duration_seconds:30});
   return send({detail:'Synthetic evidence unavailable'},404);
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');await page.getByText('Change vehicle, date or direction',{exact:true}).click();await page.getByLabel('Driver service date',{exact:true}).fill('2026-10-19');
  await page.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();
  const panel=page.getByRole('region',{name:'Next stop navigation',exact:true});const link=panel.getByRole('link',{name:'Navigate to next stop',exact:true});
  await link.waitFor();const href=await link.getAttribute('href');let u=new URL(href);
  assert.equal(u.hostname,'www.google.com');assert.equal(u.searchParams.get('destination'),'6.9,79.9');
  assert.equal(u.searchParams.get('api'),'1');assert.equal(u.searchParams.get('travelmode'),'driving');assert.equal(u.searchParams.get('dir_action'),'navigate');
  assert.equal(u.searchParams.has('waypoints'),false);assert.equal(u.searchParams.has('origin'),false);
  assert.ok((await panel.textContent()).includes('second navigation device'));
  await panel.getByRole('button',{name:'Copy link for navigation device',exact:true}).click();assert.equal(await page.evaluate(()=>window.__copiedNavigation),href);
  const popup=await Promise.all([page.waitForEvent('popup'),link.click()]);await popup[0].close();
  assert.equal(sequence,1);assert.equal(writes.length,0);await panel.getByText('Opening Maps did not advance this trip.',{exact:false}).waitFor();
  arrived=true;await panel.getByText('Arrival recorded.',{exact:false}).waitFor();assert.equal(await link.count(),0);
  await page.getByRole('button',{name:'Next stop (manual; no passenger confirmation)',exact:true}).click();
  await link.waitFor();u=new URL(await link.getAttribute('href'));assert.equal(u.searchParams.get('destination'),'-6.91,79.91');assert.deepEqual(writes,[{method:'POST',sequence:'1'}]);
  confirmed=false;await panel.getByText('Navigation is disabled.',{exact:false}).waitFor();assert.equal(await link.count(),0);
  confirmed=true;invalid=true;await page.waitForTimeout(2300);assert.equal(await link.count(),0);
  invalid=false;mismatch=true;await panel.getByText('Current authorized stop unavailable.',{exact:false}).waitFor();assert.equal(await link.count(),0);
  mismatch=false;fail=true;await panel.getByText('Controlled arrival unavailable',{exact:false}).first().waitFor();assert.equal(await link.count(),0);
  fail=false;sequence=3;await link.waitFor();u=new URL(await link.getAttribute('href'));assert.equal(u.searchParams.get('destination'),'0,0');
  arrived=true;await panel.getByText('Final saved stop reached.',{exact:false}).waitFor();assert.equal(await link.count(),0);
  assert.equal(await page.getByRole('button',{name:'Next stop (manual; no passenger confirmation)',exact:true}).count(),0);
  for(const width of [320,390]){await page.setViewportSize({width,height:844});await panel.scrollIntoViewIfNeeded();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  completed=true;await page.getByRole('button',{name:'Refresh route',exact:true}).click();await panel.waitFor({state:'detached'});
  assert.equal(writes.length,1);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({checks:['single saved target in latitude,longitude order','copy/open do not advance','authorized Next stop action remains the sole advancement','negative and zero coordinates','unconfirmed/invalid/mismatched/error data fail closed','final stop navigation then explicit closure','320/390 px mobile layout','completed trip has no navigation'],external_requests_intercepted:external.length,backend_mutations:'one mocked explicit advance only',page_errors:errors,scope:'synthetic intercepted UI, no Google requests or physical Android handoff verification'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
