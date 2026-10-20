// Synthetic intercepted presentation contracts; no actual GPS, credentials or provider calls.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{const browser=await chromium.launch({headless:true});const passed=[];
 try{
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Colombo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const savedDay=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
  const stops=['Depot','Synthetic pickup','Synthetic school'].map((name,i)=>({sequence:i+1,event_id:`UI_STOP_${i}`,location_id:`UI_LOCATION_${i}`,name,action:['start','pickup','delivery'][i],latitude:6.9+i/100,longitude:79.9+i/100,location_confirmed:true,service_seconds:0,waiting_seconds:0,driving_seconds_from_previous:60,load_before:0,load_after:0,input_source:'simulated',location_method:'manual',arrival:`${today}T06:05:00+05:30`,eta:`${today}T06:05:00+05:30`,departure:`${today}T06:05:00+05:30`,student_ids:[]}));
  const route={route_id:'UI_PARITY_ROUTE',vehicle_id:'MALABE_PP1_VAN_01',direction:'morning',service_date:today,version:91,roster_version:1,departure:`${today}T06:00:00+05:30`,generated_at:`${today}T05:00:00+05:30`,is_current:true,execution_status:'pre_trip',planning_status:'current',feasibility_status:'feasible',errors:[],planning_errors:[],stops,driving_seconds:120,service_seconds:0,waiting_seconds:0,total_duration_seconds:120,request_settings:{provider:'simulation'},provider_source:{duration_source:'simulation',requested_provider:'simulation'},capacity:20,student_count:1};
  const pmRoute={...route,route_id:'UI_PARITY_PM',version:92,direction:'afternoon',stops:[{...stops[2],sequence:1,action:'pickup'},{...stops[1],sequence:2,action:'delivery'},{...stops[0],sequence:3,action:'end'}]};
  for(const scenario of ['admin','driver-planned','driver-active','driver-completed','driver-no-trip']){
   const admin=scenario==='admin',context=await browser.newContext({viewport:{width:1366,height:900}}),calls=[],errors=[];let fail=false;
   await context.addInitScript(()=>sessionStorage.setItem('saferide.login','synthetic-presentation'));
   const state=scenario==='driver-planned'?'PLANNED':scenario==='driver-active'?'ACTIVE':'COMPLETED';
   const trip=scenario==='driver-no-trip'?null:{trip_id:'UI_CURRENT_TRIP',vehicle_id:route.vehicle_id,route_id:route.route_id,route_version:91,direction:'morning',state,route:{...route,execution_status:state==='ACTIVE'?'active':state==='COMPLETED'?'completed':'pre_trip'},unfinished_actions:[],unfinished_action_count:0};
   await context.route('**/*',r=>{
    const u=new URL(r.request().url()),p=u.pathname;
    const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
    if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();
    if(!p.startsWith('/api/'))return r.continue();calls.push({path:p,method:r.request().method()});
    if(p==='/api/auth/me')return send({id:'UI_ACCOUNT',username:'synthetic.reviewer',role:admin?'administrator':'driver',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[route.vehicle_id],student_ids:[]});
    if(p==='/api/routing/vehicles')return send([{id:route.vehicle_id,capacity:20,input_source:'simulated'}]);
    if(p==='/api/daily-plan'){
     const day=structuredClone(savedDay);day.service_date=u.searchParams.get('service_date');day.plans.morning.route=route;day.plans.morning.publication='published';day.plans.morning.publication_blockers=[];day.plans.afternoon.route=pmRoute;day.plans.afternoon.publication='published';day.plans.afternoon.publication_blockers=[];return send(day);
    }
    if(p==='/api/routes/published')return fail?send({detail:'Controlled publication failure'},503):send({published_route:u.searchParams.get('direction')==='afternoon'?pmRoute:route,publication_status:'published',trip});
    if(p==='/api/pickup-policy')return send({morning_scope:'per_stop',afternoon_scope:'per_school',demo_duration_seconds:30});
    if(p==='/api/auth/tracking')return send([{id:'UI_REVOKED_DEVICE',vehicle_id:route.vehicle_id,trip_id:'OTHER_TRIP',kind:'phone',label:'Old revoked fixture',expires_at:'2026-01-01T00:00:00Z',revoked_at:'2026-01-01T00:00:00Z'}]);
    if(p.endsWith('/positions/latest'))return send({position:{id:'UI_OLD_POSITION',sample_id:'UI_OLD_SAMPLE',vehicle_id:route.vehicle_id,trip_id:'OTHER_TRIP',source:'simulation',latitude:6.9,longitude:79.9,recorded_at:new Date().toISOString(),received_at:new Date().toISOString(),accuracy_m:5,speed_mps:null},status:'fresh',age_seconds:0,stale_after_seconds:30,movement_state:'unknown'});
    if(p==='/api/trips/UI_CURRENT_TRIP/arrival')return send({trip_id:trip.trip_id,route_id:route.route_id,state:'gps_unknown',reason:'Synthetic test without eligible current-trip GPS',gps_status:'unknown',current_stop:stops[1],observation_count:0,can_advance:false,arrival_event:null,settings:{radius_metres:50,exit_radius_metres:75,dwell_seconds:15,min_observations:3,max_gap_seconds:10,freshness_seconds:20}});
    return send({detail:'Synthetic test data unavailable'},404);
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');
   if(admin){
    await page.getByRole('heading',{name:'1. Review attendance',exact:true}).waitFor();
    assert.equal(await page.getByLabel('Daily Plan service date',{exact:true}).inputValue(),today);
    const nav=page.getByRole('navigation',{name:'Administrator workspace'});
    assert.deepEqual(await nav.getByRole('button').allTextContents(),['Daily Plan','Live Tracking','Alerts','Setup','Research & Testing']);
    assert.equal(await page.getByLabel('Controlled traffic adapter failure').count(),0);
    assert.equal(await page.getByLabel('Provisional registration event JSON').count(),0);
    assert.equal(await page.getByRole('region',{name:'Travel-time Evaluation'}).count(),0);
    await page.getByRole('heading',{name:'3. Review and publish',exact:true}).waitFor();
    await page.getByText('Version 91',{exact:false}).first().waitFor();
    assert.deepEqual(await page.locator('[aria-label="morning Daily Plan"] li').allTextContents(),stops.map(s=>`${s.sequence}. ${s.action}: ${s.name}Arrival 06:05:00 · service 06:05:00–06:05:00 · onboard 0→0`));
    await page.getByText('Version 92',{exact:false}).first().waitFor();
    const before=calls.filter(c=>c.method!=='GET').length;
    await page.getByLabel('Daily Plan service date',{exact:true}).fill('2026-10-22');await page.waitForTimeout(150);
    assert.equal(calls.filter(c=>c.method!=='GET').length,before);
   }else{
    await page.getByRole('region',{name:'Selected route summary'}).getByText('Plan v91',{exact:false}).waitFor();
    const gps=page.getByRole('region',{name:'Vehicle GPS status'});await gps.getByText('Waiting for GPS',{exact:true}).waitFor();
    assert.equal(await page.getByText('UI_OLD_POSITION',{exact:false}).count(),0);
    if(state==='ACTIVE'&&trip)await page.getByRole('region',{name:'Next stop navigation'}).getByText('Stop 2: Synthetic pickup',{exact:false}).waitFor();
    if(scenario==='driver-planned'){
     assert.equal(await page.getByRole('button',{name:'Start trip (manual prototype)',exact:true}).count(),1);
     assert.equal(await page.getByRole('button',{name:'Create planned trip (manual prototype)',exact:true}).count(),0);
    }
    if(scenario==='driver-no-trip')assert.equal(await page.getByRole('button',{name:'Create planned trip (manual prototype)',exact:true}).count(),1);
    if(scenario==='driver-completed'){
     await page.getByRole('heading',{name:'Trip route',exact:true}).waitFor();
     assert.deepEqual(await page.getByRole('list',{name:'Fixed trip actions'}).locator(':scope > li').evaluateAll(els=>els.map(e=>e.querySelector('p').textContent)),stops.map(s=>s.name));
     assert.equal(await page.getByRole('region',{name:'Next stop navigation'}).count(),0);
    }
    const sessions=page.getByText('Tracking sessions and revocation history',{exact:true});await sessions.waitFor();
    assert.equal(await page.getByText('Old revoked fixture',{exact:false}).isVisible(),false);
   }
   for(const viewport of [{width:1366,height:900},{width:390,height:844}]){
    await page.setViewportSize(viewport);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    fs.mkdirSync(path.resolve(__dirname,'../node_modules/.cache'),{recursive:true});
    await page.screenshot({path:path.resolve(__dirname,`../node_modules/.cache/presentation-${scenario}-${viewport.width}.png`)});
   }
   if(scenario==='driver-no-trip'){await page.getByText('Change vehicle, date or direction',{exact:true}).click();await page.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();await page.getByRole('region',{name:'Selected route summary'}).getByText('Plan v92',{exact:false}).waitFor();assert.deepEqual(await page.getByRole('list',{name:'Driver stored actions'}).locator(':scope > li').evaluateAll(els=>els.map(e=>e.querySelector('p').textContent)),pmRoute.stops.map(s=>s.name));}
   if(scenario==='driver-active'){const navigation=page.getByRole('region',{name:'Next stop navigation'});await navigation.scrollIntoViewIfNeeded();await page.screenshot({path:path.resolve(__dirname,'../node_modules/.cache/presentation-driver-navigation-390.png')});}
   assert.ok(calls.every(c=>c.method==='GET'));assert.ok(!calls.some(c=>/map-image|generate|geocode|predict/.test(c.path)));assert.deepEqual(errors,[]);
   passed.push(scenario);await context.close();
  }
  console.log(JSON.stringify({passed,viewports:['1366x900','390x844'],writes:0,paid_requests:0,scope:'Synthetic intercepted presentation; not new backend authorization or field verification'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
