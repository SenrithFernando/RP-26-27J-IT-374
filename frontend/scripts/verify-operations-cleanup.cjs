// UI contract checks with intercepted synthetic responses. No real credentials,
// database writes, external tiles or paid provider calls. Not end-to-end auth.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});const passed=[];
  async function scenario(role,mode,check){
    const routeFixture={route_id:'UI_ROUTE_LATEST',version:9,roster_version:2,is_current:true,service_date:'2099-01-01',generated_at:'2026-10-18T00:00:00Z',provider_source:{duration_source:'google_live'},stops:[],driving_seconds:123,service_seconds:20,waiting_seconds:0,total_duration_seconds:143};
    const context=await browser.newContext();const errors=[];
    await context.addInitScript(()=>sessionStorage.setItem('saferide.login','ui-contract-test-only'));
    await context.route('**/*',async route=>{
      const u=new URL(route.request().url()),p=u.pathname.replace(/^\/api/,'');
      const respond=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
      if(!u.pathname.startsWith('/api/'))return ['localhost','127.0.0.1'].includes(u.hostname)?route.continue():route.abort();
      if(p==='/auth/me')return respond({id:'UI_ONLY',username:'ui.test',role,mode:mode==='demo-workspace'?'demo':'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:role==='driver'?['UI_VAN']:[],student_ids:role==='parent'?['UI_CHILD']:[]});
      if(mode==='failure')return respond({detail:'Controlled backend unavailable'},503);
      if(p==='/routing/vehicles')return respond(mode==='empty'?[]:[{id:'UI_VAN',capacity:2,input_source:'simulated'}]);
      if(p==='/routing/students'||p==='/routing/schools')return respond([]);
      if(p==='/routes/latest')return mode==='saved-stale-gps'?respond(routeFixture):respond({detail:'No saved route'},404);
      if(p.startsWith('/routing/plans/'))return respond({is_current:false,route_id:null,roster_version:1,generation_status:'unconfigured',errors:[]});
      if(p==='/trips/current')return respond({trip:mode==='saved-stale-gps'?{trip_id:'UI_TRIP_PINNED',state:'ACTIVE',direction:'morning',route_id:'UI_ROUTE_OLD',route_version:8,route:{...routeFixture,route_id:'UI_ROUTE_OLD',version:8,provider_source:{duration_source:'ml_prediction'}}}:null});
      if(p.endsWith('/positions/latest'))return respond({position:mode==='saved-stale-gps'?{id:'UI_POSITION',sample_id:'UI_SAMPLE',vehicle_id:'UI_VAN',trip_id:'UI_TRIP_PINNED',source:'simulation',latitude:6.9,longitude:79.9,speed_mps:3,recorded_at:'2020-01-01T00:00:00Z',received_at:'2020-01-01T00:00:01Z'}:null,age_seconds:null,status:mode==='saved-stale-gps'?'stale':'unknown',stale_after_seconds:30,movement_state:'unknown',note:'Synthetic contract fixture'});
      if(p==='/routing/notifications')return respond({notifications:[],unread_count:0,truncated:false,next_before_order_id:null});
      if(p.startsWith('/parent/students/'))return respond({name:'Synthetic UI child',school_name:'Synthetic school',vehicle_id:'UI_VAN',input_source:'simulated',active:true,note:'Permitted summary'});
      if(p==='/ml/status')return respond({available:false,reason:'No model in UI fixture'});
      if(p==='/traffic/status')return respond({google:{configured:false,reason:'No live provider in UI fixture'}});
      return respond({detail:'Unconfigured UI fixture endpoint'},404);
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    try{await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://localhost:5173');await page.getByRole('button',{name:'Log out',exact:true}).waitFor();if(role==='administrator'&&mode!=='demo-workspace')await page.getByRole('button',{name:'Live Tracking',exact:true}).click();await check(page);assert.deepEqual(errors,[]);passed.push(`${role}: ${mode}`);}finally{await context.close();}
  }
  try{
    await scenario('administrator','failure',async p=>{
      await p.getByText('Vehicles could not be loaded.',{exact:false}).waitFor();
      assert.equal(await p.getByText('BUS-01',{exact:false}).count(),0);
      await p.getByRole('button',{name:'Research & Testing',exact:true}).click();await p.getByRole('button',{name:'Routes',exact:true}).click();await p.getByText('Controlled backend unavailable',{exact:false}).first().waitFor();
      await p.getByRole('button',{name:'Alerts',exact:true}).click();await p.getByText('No mock events are substituted.',{exact:false}).waitFor();
    });
    await scenario('administrator','empty',async p=>{await p.getByLabel('Fleet vehicle',{exact:true}).getByText('No vehicles available',{exact:true}).waitFor({state:'attached'});});
    await scenario('administrator','no-trip-no-gps',async p=>{
      await p.getByText('No trip is currently active.',{exact:true}).waitFor();
      await p.getByText('No saved route to display.',{exact:true}).waitFor();
      await p.getByText('Previous journeys are not shown as live tracking.',{exact:false}).waitFor();
    });
    await scenario('administrator','saved-stale-gps',async p=>{
      await p.getByText('Trip in progress',{exact:true}).waitFor();assert.equal(await p.getByLabel('Fleet direction',{exact:true}).isDisabled(),true);
      await p.getByText('Version 8',{exact:false}).waitFor();
      await p.getByText('Signal out of date',{exact:true}).waitFor();
      await p.getByText('Simulated GPS',{exact:false}).waitFor();
      await p.getByText('Current movement is unknown.',{exact:false}).waitFor();
      assert.equal(await p.getByText('Google Maps traffic-aware estimate',{exact:true}).count(),0);
      await p.getByText('ML prediction',{exact:false}).waitFor();
    });
    await scenario('driver','no-trip-no-gps',async p=>{
      await p.getByText('No persisted trip for this vehicle.',{exact:true}).waitFor();
      await p.getByText('Waiting for the tracking phone to send its position.',{exact:false}).waitFor();
      assert.equal(await p.getByText('BUS-01',{exact:false}).count(),0);
    });
    await scenario('driver','failure',async p=>{await p.getByText('Vehicles unavailable:',{exact:false}).waitFor();});
    await scenario('parent','no-trip-no-gps',async p=>{
      await p.getByRole('heading',{name:'Synthetic UI child',exact:true}).waitFor();
      await p.getByText('Registration input: simulated',{exact:false}).waitFor();
      await p.getByText('Unavailable in this permitted parent summary.',{exact:false}).waitFor();
      await p.getByText('No stored missed-pickup events for this recipient.',{exact:true}).waitFor();
    });
    await scenario('parent','failure',async p=>{await p.getByText('Controlled backend unavailable',{exact:true}).waitFor();assert.equal(await p.getByRole('heading',{name:'Synthetic UI child'}).count(),0);});
    await scenario('administrator','demo-workspace',async p=>{
      await p.getByText('SYNTHETIC DEMO',{exact:false}).first().waitFor();
      await p.getByRole('heading',{name:'Choose Interface',exact:true}).waitFor();
      assert.equal(await p.getByRole('region',{name:'Authorized fleet operations'}).count(),0);
    });
    console.log(JSON.stringify({passed,scope:'Intercepted UI contracts only; no external calls or existing-record changes'},null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
