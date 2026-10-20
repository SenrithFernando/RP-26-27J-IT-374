// Isolated synthetic browser fixtures. No application DB writes or paid requests.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187';
const folder=process.env.SAFERIDE_SCREENSHOT_DIR||path.resolve(__dirname,'../node_modules/.cache/workspace-cards');
const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Colombo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const vehicle='MALABE_PP1_VAN_01';
const stops=['Depot','Landmark pickup','Horizon College International','Boys’ Model College'].map((name,i)=>({sequence:i+1,event_id:`CARD_STOP_${i}`,location_id:`CARD_POINT_${i}`,name,action:i===0?'start':i===1?'pickup':'delivery',school_id:i>1?`SCH_${i===2?'A':'B'}`:null,grouped:i>1,latitude:6.90+i*.003,longitude:79.95+i*.003,location_confirmed:true,service_seconds:i>1?600:i===1?120:0,waiting_seconds:0,driving_seconds_from_previous:i?120:0,load_before:0,load_after:0,input_source:'simulated',location_method:'manual',arrival:`${today}T0${i<2?'6':'7'}:${i%2?'05':'00'}:00+05:30`,eta:`${today}T07:00:00+05:30`,departure:`${today}T07:10:00+05:30`,student_ids:[]}));
const route={route_id:'CARD_SAVED_ROUTE',vehicle_id:vehicle,direction:'morning',service_date:today,version:91,roster_version:2,departure:`${today}T06:20:00+05:30`,generated_at:`${today}T05:00:00+05:30`,is_current:true,execution_status:'pre_trip',planning_status:'current',feasibility_status:'feasible',errors:[],planning_errors:[],stops,driving_seconds:360,service_seconds:1320,waiting_seconds:0,total_duration_seconds:1680,request_settings:{provider:'simulation'},provider_source:{duration_source:'simulation'},capacity:20,student_count:8};
const pm={...route,route_id:'CARD_PM_ROUTE',version:92,direction:'afternoon',departure:`${today}T13:30:00+05:30`};
const fixture=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true}),passed=[];fs.mkdirSync(folder,{recursive:true});
 try{
  for(const scenario of ['admin','planned','active','active-draft','completed','unpublished','error','no-trip']){
   const admin=scenario==='admin',context=await browser.newContext({viewport:{width:1366,height:900}}),requests=[],errors=[];
   let state=scenario.startsWith('active')?'ACTIVE':scenario==='completed'?'COMPLETED':'PLANNED',made=!['unpublished','error','no-trip'].includes(scenario),publication='draft',failSave=false,releasePublish,enrolled=false,revoked=false;
   await context.addInitScript(()=>{sessionStorage.setItem('saferide.login','synthetic-cards-test');Object.defineProperty(navigator,'geolocation',{configurable:true,value:{watchPosition(ok){window.cardGps=ok;return 1;},clearWatch(){window.cardClears=(window.cardClears||0)+1;}}});});
   const trip=()=>made?{trip_id:'CARD_FIXED_TRIP',vehicle_id:vehicle,route_id:route.route_id,route_version:91,direction:'morning',state,adult_phone_field_test_authorized:true,route:{...route,execution_status:state==='ACTIVE'?'active':state==='COMPLETED'?'completed':'pre_trip'},unfinished_actions:scenario==='active'?[{event_id:'CARD_PENDING',sequence:2,action:'delivery',student_name:'Synthetic participant',name:'Landmark',status:'PENDING'}]:[],unfinished_action_count:scenario==='active'?1:0}:null;
   await context.route('**/*',async r=>{
    const u=new URL(r.request().url()),p=u.pathname,method=r.request().method();
    const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
    if(process.env.SAFERIDE_ALLOW_OSM_TILES==='1'&&u.hostname.endsWith('.tile.openstreetmap.org'))return r.continue();
    if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();
    if(!p.startsWith('/api/'))return r.continue();requests.push({p,method,query:u.searchParams.toString(),body:method==='POST'?r.request().postDataJSON():null});
    if(p==='/api/auth/me')return send({id:'CARD_ACCOUNT',username:'synthetic.reviewer',role:admin?'administrator':'driver',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[vehicle],student_ids:[]});
    if(p==='/api/routing/vehicles')return send([{id:vehicle,capacity:20,input_source:'simulated'}]);
    if(p==='/api/daily-plan'){
     const day=structuredClone(fixture);day.service_date=u.searchParams.get('service_date');day.plans.morning.route={...route,service_date:day.service_date};day.plans.afternoon.route={...pm,service_date:day.service_date};
     for(const d of ['morning','afternoon']){day.plans[d].publication=publication;day.plans[d].publication_blockers=[];}return send(day);
    }
    if(p==='/api/daily-plan/import')return failSave?send({detail:'Controlled save failure'},503):send({regenerated:[]});
    if(p==='/api/daily-plan/generate')return send({});
    if(p==='/api/daily-plan/publish'){await new Promise(resolve=>releasePublish=resolve);publication='published';return send({publication:'published'});}
    if(p==='/api/routes/latest')return send(route);
    if(p.startsWith('/api/routing/plans/'))return send({route_id:route.route_id,roster_version:2,is_current:true,errors:[]});
    if(p==='/api/trips/current')return send({trip:trip()});
    if(p==='/api/routes/published')return scenario==='error'?send({detail:'Controlled backend unavailable'},503):send({published_route:['unpublished','active-draft'].includes(scenario)?null:u.searchParams.get('direction')==='afternoon'?pm:route,publication_status:['unpublished','active-draft'].includes(scenario)?'draft':'published',trip:trip()});
    if(p==='/api/routing/notifications')return send({notifications:[],unread_count:0,truncated:false});
    if(p==='/api/pickup-policy')return send({morning_scope:'per_stop',afternoon_scope:'per_school',demo_duration_seconds:30});
    if(p==='/api/auth/tracking')return send(enrolled?[{id:'CARD_DEVICE',vehicle_id:vehicle,trip_id:'CARD_FIXED_TRIP',kind:'phone',label:'Synthetic UI session',expires_at:new Date(Date.now()+3600000).toISOString(),revoked_at:revoked?new Date().toISOString():null}]:[]);
    if(p==='/api/tracking/enroll'){const body=r.request().postDataJSON();assert.equal(body.vehicle_id,vehicle);assert.equal(body.trip_id,'CARD_FIXED_TRIP');assert.equal(body.kind,'phone');enrolled=true;return send({credential:'synthetic-scoped-test-only',expires_at:new Date(Date.now()+3600000).toISOString()});}
    if(p==='/api/tracking/positions'){const sample=r.request().postDataJSON();assert.equal('vehicle_id' in sample,false);assert.equal('trip_id' in sample,false);assert.equal('source' in sample,false);return send({sample:{...sample,received_at:new Date().toISOString(),accuracy_quality:'acceptable'},duplicate:false});}
    if(p==='/api/tracking/CARD_DEVICE/revoke'){revoked=true;return send({});}
    if(p==='/api/trips'&&method==='POST'){assert.equal(r.request().postDataJSON().route_id,route.route_id);made=true;state='PLANNED';return send(trip(),201);}
    if(p==='/api/trips/CARD_FIXED_TRIP/start'){state='ACTIVE';return send(trip());}
    if(p==='/api/trips/CARD_FIXED_TRIP/complete'){state='COMPLETED';return send(trip());}
    if(p.endsWith('/positions/latest'))return send({position:{id:'DO_NOT_DISPLAY_HISTORY',sample_id:'SYNTHETIC_ONLY',vehicle_id:vehicle,trip_id:'OTHER_TRIP',source:'simulation',latitude:6.9,longitude:79.95,recorded_at:new Date().toISOString(),received_at:new Date().toISOString(),accuracy_m:5,speed_mps:null},status:'fresh',stale_after_seconds:60,age_seconds:0});
    if(p.endsWith('/arrival'))return send({trip_id:'CARD_FIXED_TRIP',route_id:route.route_id,state:'gps_unknown',current_stop:stops[1],arrival_event:null,can_advance:false,distance_metres:null,observation_count:0,reason:'No eligible GPS for this trip',settings:{}});
    if(p.endsWith('/operational-events'))return send({episodes:[],gps_state:'unknown',geometry:null});
    if(p.endsWith('/pickup-windows'))return send({trip_id:'CARD_FIXED_TRIP',settings:null,windows:[],server_now:new Date().toISOString()});
    return send({detail:'Fixture endpoint unavailable'},404);
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(12000);await page.goto(base);
   if(admin){
    await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();await page.getByLabel('Overview vehicle').waitFor();
    assert.equal(await page.getByRole('heading',{level:1}).count(),1);assert.equal(await page.getByRole('region',{name:'Authorized fleet operations'}).count(),0);
    await page.getByText('Authorized vehicles',{exact:true}).waitFor();
    await page.locator('.leaflet-container').waitFor();await page.waitForTimeout(1200);await page.screenshot({path:path.join(folder,'administrator-overview-desktop.png')});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(folder,'administrator-overview-phone.png')});
    await page.getByRole('button',{name:'Open navigation',exact:true}).click();await page.getByRole('button',{name:'Daily Plan',exact:true}).click();
    await page.getByRole('button',{name:'Edit attendance',exact:true}).waitFor();
    assert.equal(await page.getByLabel('TEST_01 am attendance',{exact:true}).count(),0);
    assert.equal(await page.locator('details').count(),0);
    await page.screenshot({path:path.join(folder,'administrator-daily-plan-phone.png')});await page.setViewportSize({width:1366,height:900});await page.screenshot({path:path.join(folder,'administrator-daily-plan-desktop.png')});
    await page.getByRole('button',{name:'Edit attendance',exact:true}).click();const edit=page.getByRole('dialog',{name:'Edit attendance',exact:true});await edit.waitFor();await page.screenshot({path:path.join(folder,'administrator-attendance-desktop.png')});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(folder,'administrator-attendance-phone.png')});await page.setViewportSize({width:1366,height:900});await edit.getByLabel('TEST_01 am attendance',{exact:true}).selectOption('no');failSave=true;await edit.getByRole('button',{name:'Save dated attendance',exact:true}).click();await edit.getByText('Controlled save failure',{exact:true}).waitFor();assert.equal(await edit.getByLabel('TEST_01 am attendance',{exact:true}).inputValue(),'no');failSave=false;await edit.getByRole('button',{name:'Save dated attendance',exact:true}).click();await edit.waitFor({state:'hidden'});
    await page.getByRole('button',{name:'Open AM route',exact:true}).click();const itinerary=page.getByRole('dialog',{name:'Morning route',exact:true});await itinerary.getByRole('list',{name:'morning ordered stops'}).waitFor();assert.deepEqual(await itinerary.getByRole('list').locator('li p:first-child').allTextContents(),stops.map(s=>s.name));await itinerary.getByRole('button',{name:'Close Morning route',exact:true}).click();
    const date=page.getByLabel('Daily Plan service date',{exact:true}),writes=requests.filter(r=>r.method!=='GET').length;await date.fill('2026-10-22');await page.waitForTimeout(100);assert.equal(requests.filter(r=>r.method!=='GET').length,writes);
    await page.getByRole('button',{name:'Prepare routes',exact:true}).click();const prepare=page.getByRole('dialog',{name:'Prepare routes',exact:true});await prepare.getByRole('button',{name:'Validate AM override',exact:true}).click();await prepare.getByText('Saved route generation completed; review the draft.',{exact:true}).waitFor();assert.equal(requests.find(r=>r.p==='/api/daily-plan/generate').body.provider,'simulation');await prepare.getByRole('button',{name:'Close Prepare routes',exact:true}).click();
    await page.getByRole('button',{name:'Publish reviewed AM plan',exact:true}).click();await page.waitForFunction(()=>document.body.textContent.includes('Saving / planning'));assert.equal(await page.getByText('Your review has been saved. The published plan is available to the assigned driver.',{exact:true}).count(),0);releasePublish();await page.getByText('Your review has been saved. The published plan is available to the assigned driver.',{exact:true}).waitFor();
   }else{
    await page.getByRole('region',{name:'Selected route summary'}).waitFor();
    if(scenario==='error')await page.getByText('Controlled backend unavailable',{exact:false}).first().waitFor();
    else if(scenario==='unpublished'){await page.getByText('No current published morning route',{exact:false}).waitFor();assert.equal(await page.getByRole('button',{name:'Prepare trip',exact:true}).count(),0);}
    else if(scenario.startsWith('active')){await page.getByRole('link',{name:'Navigate to next stop',exact:true}).waitFor();assert.equal(await page.getByText('DO_NOT_DISPLAY_HISTORY',{exact:false}).count(),0);assert.equal(await page.locator('.saferide-position-marker').count(),0);if(scenario==='active-draft')await page.getByText('Planning: draft.',{exact:false}).waitFor();}
    else if(scenario==='planned')await page.getByRole('button',{name:'Start trip',exact:true}).waitFor();
    else if(scenario==='completed'){await page.getByRole('button',{name:'View itinerary',exact:true}).click();const fixed=page.getByRole('dialog',{name:'Fixed trip itinerary',exact:true});await fixed.getByRole('list',{name:'Fixed trip actions'}).waitFor();assert.deepEqual(await fixed.getByRole('list').locator('li p:first-child').allTextContents(),stops.map(s=>s.name));await fixed.getByRole('button',{name:'Close Fixed trip itinerary',exact:true}).click();}
    else if(scenario==='no-trip'){await page.getByRole('button',{name:'Prepare trip',exact:true}).click();const prep=page.getByRole('dialog',{name:'Prepare trip',exact:true});await prep.getByRole('button',{name:'Create planned trip',exact:true}).click();await page.getByRole('button',{name:'Start trip',exact:true}).waitFor();assert.equal(requests.filter(r=>r.p==='/api/trips/CARD_FIXED_TRIP/start').length,0);await page.getByRole('button',{name:'Start trip',exact:true}).click();await page.getByRole('link',{name:'Navigate to next stop',exact:true}).waitFor();}
    assert.equal(await page.locator('details').count(),0);assert.equal(await page.locator('footer').count(),0);assert.equal(await page.locator('header').count(),1);
    for(const width of [1366,390]){
     await page.setViewportSize({width,height:width===390?844:900});await page.waitForTimeout(200);await page.screenshot({path:path.join(folder,`driver-${scenario}-${width===390?'phone':'desktop'}.png`)});
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     const map=await page.getByRole('region',{name:'Driver route map'}).boundingBox();assert.ok(map.y<(['unpublished','error'].includes(scenario)?400:300),`Driver map begins at ${map.y}`);
    }
    if(scenario==='active'){
     await page.getByRole('button',{name:'GPS controls',exact:true}).click();const gps=page.getByRole('dialog',{name:'GPS controls',exact:true});
     await gps.waitFor();await page.screenshot({path:path.join(folder,'driver-gps-controls-phone.png')});await gps.getByRole('button',{name:'Enroll phone sender for active trip',exact:true}).click();await gps.getByRole('button',{name:'Start sharing',exact:true}).click();await page.waitForFunction(()=>!!window.cardGps);
     await page.evaluate(()=>window.cardGps({timestamp:Date.now(),coords:{latitude:6.9,longitude:79.95,accuracy:8,speed:null}}));await gps.getByText('Sharing — upload accepted',{exact:false}).waitFor();
     const clears=await page.evaluate(()=>window.cardClears||0);await gps.getByRole('button',{name:'Close GPS controls',exact:true}).click();await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>window.cardClears||0),clears);
     await page.getByText('Sharing: Sharing — upload accepted',{exact:true}).waitFor();
     await page.getByRole('button',{name:'GPS controls',exact:true}).click();await gps.getByRole('button',{name:'Stop sharing',exact:true}).click();assert.ok(await page.evaluate(()=>window.cardClears)>clears);
     await gps.getByRole('button',{name:'Manage GPS sessions',exact:true}).click();const sessions=page.getByRole('dialog',{name:'GPS sessions',exact:true});await sessions.getByRole('button',{name:'Revoke',exact:true}).click();await sessions.getByText('Revoked / expires',{exact:false}).waitFor();await sessions.getByRole('button',{name:'Close GPS sessions',exact:true}).click();await gps.getByRole('button',{name:'Close GPS controls',exact:true}).click();
     await page.getByRole('button',{name:'End trip',exact:true}).click();const end=page.getByRole('dialog',{name:'End trip',exact:true});await end.getByText('1 passenger actions remain unconfirmed.',{exact:false}).waitFor();assert.equal(requests.filter(r=>r.p.endsWith('/complete')).length,0);await end.getByRole('button',{name:'Confirm end trip',exact:true}).click();await page.getByRole('region',{name:'Selected route summary'}).getByText('COMPLETED',{exact:true}).waitFor();await page.getByText('1 unconfirmed',{exact:true}).waitFor();assert.equal(requests.filter(r=>/pickup.*confirm/.test(r.p)).length,0);
    }
   }
   assert.equal(await page.locator('details').count(),0);assert.equal(requests.some(r=>/map-image|geocode|predict/.test(r.p)),false);assert.deepEqual(errors,[]);
   if(!admin&&!['no-trip','active'].includes(scenario))assert.ok(requests.every(r=>r.method==='GET'));
   passed.push(scenario);await context.close();
  }
  console.log(JSON.stringify({passed,viewports:['1366x900','390x844'],screenshots:folder,scope:'Synthetic intercepted browser UI; no real records, paid APIs or physical-phone evidence'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
