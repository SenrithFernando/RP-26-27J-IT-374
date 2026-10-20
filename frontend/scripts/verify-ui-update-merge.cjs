// Isolated intercepted UI fixtures: no real accounts, records, geolocation or paid requests.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{const browser=await chromium.launch({headless:true}),passed=[];
 const base=process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187';
 const folder=path.resolve(__dirname,'../node_modules/.cache');fs.mkdirSync(folder,{recursive:true});
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Colombo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const stops=['Synthetic school','Synthetic landmark','Synthetic depot'].map((name,i)=>({sequence:i+1,event_id:`FIXTURE_STOP_${i}`,location_id:`FIXTURE_POINT_${i}`,name,action:i===0?'pickup':i===1?'delivery':'end',latitude:6.9+i/100,longitude:79.9+i/100,location_confirmed:true,service_seconds:120,waiting_seconds:0,driving_seconds_from_previous:60,load_before:0,load_after:0,input_source:'simulated',location_method:'manual',arrival:`${today}T13:30:00+05:30`,eta:`${today}T13:30:00+05:30`,departure:`${today}T13:32:00+05:30`,student_ids:[]}));
 const route={route_id:'UI_UPDATE_PLAN',vehicle_id:'MALABE_PP1_VAN_01',direction:'morning',service_date:today,version:81,roster_version:1,departure:`${today}T06:00:00+05:30`,generated_at:`${today}T05:00:00+05:30`,is_current:true,execution_status:'pre_trip',planning_status:'current',feasibility_status:'feasible',errors:[],planning_errors:[],stops,driving_seconds:120,service_seconds:360,waiting_seconds:0,total_duration_seconds:480,request_settings:{provider:'simulation'},provider_source:{duration_source:'simulation'},capacity:20,student_count:1};
 const activeRoute={...route,route_id:'UI_UPDATE_FIXED',direction:'afternoon',version:80,execution_status:'active'};
 const day=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
 try{
  for(const scenario of ['planned','active','stale','poor','missing-speed','wrong-trip','missing-route','route-error','empty']){
   const context=await browser.newContext({viewport:{width:1366,height:900}}),requests=[],errors=[];
   await context.addInitScript(()=>sessionStorage.setItem('saferide.login','isolated-ui-update'));
   const active=!['planned','missing-route','route-error','empty'].includes(scenario);
   await context.route('**/*',r=>{
    const u=new URL(r.request().url()),p=u.pathname;const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
    if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();if(!p.startsWith('/api/'))return r.continue();requests.push({method:r.request().method(),path:p,trip:u.searchParams.get('trip_id')});
    if(p==='/api/auth/me')return send({id:'FIXTURE_ADMIN',username:'synthetic.reviewer',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
    if(p==='/api/daily-plan')return send(day);
    if(p==='/api/routing/vehicles')return send(scenario==='empty'?[]:[{id:route.vehicle_id,capacity:20,input_source:'simulated'}]);
    if(p==='/api/routes/latest')return ['missing-route','route-error'].includes(scenario)?send({detail:scenario==='missing-route'?'No saved route':'Controlled route failure'},scenario==='missing-route'?404:503):send(route);
    if(p.startsWith('/api/routing/plans/'))return send({is_current:true,route_id:route.route_id,roster_version:1,errors:[]});
    if(p==='/api/trips/current')return send({trip:active?{trip_id:'UI_ACTIVE',state:'ACTIVE',route:activeRoute,route_id:activeRoute.route_id,route_version:80,vehicle_id:route.vehicle_id,direction:'afternoon'}:scenario==='planned'?{trip_id:'UI_PLANNED',state:'PLANNED',route,route_id:route.route_id,route_version:81,vehicle_id:route.vehicle_id,direction:'morning'}:null});
    if(p.endsWith('/positions/latest'))return send({position:{id:'NEVER_DISPLAY_RAW_POSITION',sample_id:'NEVER_DISPLAY_SAMPLE',vehicle_id:route.vehicle_id,trip_id:scenario==='wrong-trip'?'OTHER_TRIP':'UI_ACTIVE',source:'simulation',latitude:6.905,longitude:79.905,speed_mps:scenario==='missing-speed'?null:4,accuracy_m:scenario==='poor'?95.4:7.8,accuracy_quality:scenario==='poor'?'poor':'acceptable',recorded_at:new Date(Date.now()-(scenario==='stale'?300000:0)).toISOString(),received_at:new Date().toISOString()},status:'fresh',age_seconds:0,stale_after_seconds:30,movement_state:'unknown'});
    if(p.endsWith('/arrival'))return send({trip_id:'UI_ACTIVE',route_id:activeRoute.route_id,current_stop:stops[0],state:'gps_unknown'});
    return send({detail:'Synthetic endpoint unavailable'},404);
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base);
   await page.getByRole('button',{name:'Live Fleet',exact:true}).click();const fleet=page.getByRole('region',{name:'Authorized fleet operations'});
   if(scenario==='empty'){await fleet.getByLabel('Fleet vehicle').getByText('No vehicles available').waitFor({state:'attached'});}
   else{
    await fleet.getByText('Estimated route duration',{exact:true}).waitFor();
    if(scenario==='planned'){
     await fleet.getByText('Not started',{exact:true}).waitFor();await fleet.getByText('Previous journeys are not shown as live tracking.',{exact:true}).waitFor();assert.equal(requests.some(r=>r.path.endsWith('/positions/latest')),false);
    }else if(scenario==='missing-route')await fleet.getByText('No saved route to display.',{exact:true}).waitFor();
    else if(scenario==='route-error')await fleet.getByText('Controlled route failure',{exact:false}).waitFor();
    else{
     const gps=fleet.getByRole('region',{name:'Vehicle GPS status'});
     await gps.getByText(scenario==='stale'?'Signal out of date':scenario==='poor'?'Low accuracy':scenario==='wrong-trip'?'Waiting for GPS':'Location updated',{exact:true}).waitFor();
     assert.equal(await fleet.getByLabel('Fleet direction').inputValue(),'afternoon');assert.equal(await fleet.getByLabel('Fleet direction').isDisabled(),true);
     await fleet.getByText('Version 80',{exact:false}).waitFor();
     assert.ok(requests.filter(r=>r.path.endsWith('/positions/latest')).every(r=>r.trip==='UI_ACTIVE'));
     const shouldPlot=['active','missing-speed'].includes(scenario);
     await page.waitForTimeout(100);assert.equal(await fleet.locator('.saferide-position-marker').count(),shouldPlot?1:0);
     if(scenario==='missing-speed')assert.equal(await gps.getByText('Unavailable',{exact:true}).count(),1);
     if(scenario==='active')await gps.getByText('14 km/h',{exact:true}).waitFor();
     assert.equal(await fleet.getByText('NEVER_DISPLAY_RAW_POSITION',{exact:false}).count(),0);
    }
   }
   for(const width of [1366,390]){
    await page.setViewportSize({width,height:width===390?844:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(['planned','active','stale'].includes(scenario))await page.screenshot({path:path.join(folder,`ui-update-${scenario}-${width}.png`)});
   }
   assert.ok(requests.every(r=>r.method==='GET'));assert.ok(!requests.some(r=>/map-image|geocode|generate|predict/.test(r.path)));assert.deepEqual(errors,[]);passed.push(scenario);await context.close();
  }
  // Publication is shown only after a successful HTTP response, never on initial load or rejection.
  const context=await browser.newContext({viewport:{width:390,height:844}});await context.addInitScript(()=>sessionStorage.setItem('saferide.login','isolated-publication'));
  let release,publication='draft',publishCount=0,reject=false;const errors=[];
  await context.route('**/*',async r=>{
   const u=new URL(r.request().url()),p=u.pathname;const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
   if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();if(!p.startsWith('/api/'))return r.continue();
   if(p==='/api/auth/me')return send({id:'FIXTURE_ADMIN',username:'synthetic.reviewer',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
   if(p==='/api/daily-plan'){const value=structuredClone(day);value.service_date=u.searchParams.get('service_date');value.plans.morning.route=route;value.plans.morning.publication=publication;value.plans.morning.publication_blockers=[];return send(value);}
   if(p==='/api/daily-plan/publish'){publishCount++;if(reject)return send({detail:'Controlled publication rejected'},409);await new Promise(resolve=>release=resolve);publication='published';return send({publication:'published'});}
   if(p==='/api/daily-plan/import')return send({regenerated:[{status:'invalid_input'}]});
   return send({detail:'Synthetic endpoint unavailable'},404);
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.getByRole('button',{name:'Open navigation',exact:true}).click();await page.getByRole('button',{name:'Daily Plan',exact:true}).click();
  const confirmation=page.getByText('Your review has been saved. The published plan is available to the assigned driver.',{exact:true});
  const publish=page.getByRole('button',{name:'Publish reviewed AM plan',exact:true});await publish.waitFor();assert.equal(await confirmation.count(),0);await publish.click();
  await page.waitForFunction(()=>document.querySelector('[role="status"]')?.textContent?.includes('Saving'));
  assert.equal(await confirmation.count(),0);assert.equal(publishCount,1);release();await confirmation.waitFor();
  assert.ok((await confirmation.locator('xpath=../..').getAttribute('class')).includes('bg-emerald-50'));
  await confirmation.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(folder,'ui-update-published-390.png')});
  reject=true;publication='draft';await page.getByLabel('Daily Plan service date',{exact:true}).fill('2026-10-22');await publish.waitFor();await publish.click();await page.getByText('Controlled publication rejected',{exact:false}).waitFor();assert.equal(await confirmation.count(),0);
  await page.getByRole('button',{name:'Edit attendance',exact:true}).click();await page.getByRole('button',{name:'Save dated attendance',exact:true}).click();const blocked=page.getByText('Input saved; routing is blocked or failed.',{exact:false});await blocked.waitFor();assert.ok((await blocked.locator('xpath=../..').getAttribute('class')).includes('bg-amber-50'));
  assert.deepEqual(errors,[]);await context.close();passed.push('publication acknowledgement/rejection/blocked notice');
  console.log(JSON.stringify({passed,viewports:['1366x900','390x844'],scope:'Intercepted source-update merge checks; no database writes, actual phone evidence or paid requests'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
