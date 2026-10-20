// Synthetic intercepted UI contracts only. No backend writes or external requests.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});const passed=[];
 try{
  for(const mode of ['completed-am','active-pm','legacy-am','historical-am','wrong-direction','no-route','error']){
   console.log('Checking',mode);
   const context=await browser.newContext({viewport:{width:320,height:568}});
   await context.addInitScript(()=>sessionStorage.setItem('saferide.login','ui-duration-test-only'));
   const direction=mode.includes('pm')?'afternoon':'morning';
   const route={route_id:'UI_SAVED_ROUTE',version:39,vehicle_id:'UI_VAN',direction,service_date:'2026-10-19',
    departure:'2026-10-19T06:00:00+05:30',generated_at:'2026-10-19T05:00:00+05:30',
    departure_seconds:21600,feasibility_status:'feasible',errors:[],planning_errors:[],stops:[],
    driving_seconds:1067,service_seconds:2160,waiting_seconds:0,total_duration_seconds:3227,
    is_current:mode==='active-pm',execution_status:mode==='completed-am'?'completed':'pre_trip',
    roster_version:1,planning_status:'ready',student_count:8,capacity:20,request_settings:{provider:'simulation'},
    provider_source:{duration_source:'simulation'},end_policy:direction==='morning'?'last_school_no_depot_return':'SCH_B_then_SCH_A_then_homes_then_depot'};
   if(mode==='legacy-am'){delete route.driving_seconds;route.waiting_seconds=null;delete route.total_duration_seconds;}
   const trip=mode==='completed-am'||mode==='active-pm'||mode==='wrong-direction'?{
    trip_id:'UI_TRIP',vehicle_id:'UI_VAN',direction:mode==='wrong-direction'?'afternoon':direction,
    route_id:'UI_PINNED_ROUTE',route_version:38,state:mode==='completed-am'?'COMPLETED':'ACTIVE',
    route:{...route,route_id:'UI_PINNED_ROUTE',version:38,direction:mode==='wrong-direction'?'afternoon':direction,
     driving_seconds:1000,total_duration_seconds:3160},unfinished_actions:[],unfinished_action_count:0}:null;
   const errors=[];let mutations=0;
   await context.route('**/*',r=>{
    const u=new URL(r.request().url()),p=u.pathname;
    const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
    if(!p.startsWith('/api/'))return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort();
    if(r.request().method()!=='GET')mutations++;
    if(p==='/api/auth/me')return send({id:'UI_DRIVER',username:'synthetic.driver',role:'driver',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:['UI_VAN'],student_ids:[]});
    if(p==='/api/routing/vehicles')return send([{id:'UI_VAN',capacity:20,input_source:'simulated'}]);
    if(p==='/api/routes/published')return mode==='error'?send({detail:'Controlled unavailable backend'},503):send({
     publication_status:'published',published_route:['completed-am','no-route'].includes(mode)?null:route,trip:mode==='no-route'?null:trip});
    if(p.endsWith('/positions/latest'))return send({position:null,status:'unknown',age_seconds:null});
    if(p==='/api/auth/tracking')return send([]);
    if(p==='/api/pickup-policy')return send({morning_scope:'per_stop',afternoon_scope:'per_school',demo_duration_seconds:30});
    return send({detail:'No synthetic UI evidence'},404);
   });
   const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>{errors.push(e.message);console.error('Page error:',e.message);});
   await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');
   await page.getByLabel('Driver service date',{exact:true}).fill('2026-10-19');
   if(direction==='afternoon')await page.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();
   await page.waitForFunction(()=>!document.querySelector('[aria-label="Refreshing route"]'));
   const summary=page.getByRole('region',{name:'Saved planned durations',exact:true}).first();
   if(mode==='error')await page.getByText('Controlled unavailable backend',{exact:false}).waitFor();
   else if(mode!=='no-route')await summary.getByTestId('duration-route').waitFor();
   if(mode==='legacy-am'){
    assert.equal(await summary.getByTestId('planned-driving_seconds').textContent(),'Unknown');
    assert.equal(await summary.getByTestId('planned-waiting_seconds').textContent(),'Unknown');
    await summary.getByText('Older or incomplete saved snapshot:',{exact:false}).waitFor();
   }else if(['error','no-route'].includes(mode)){
    assert.equal(await summary.getByTestId('planned-total_duration_seconds').textContent(),'Unknown');
   }else{
    assert.equal(await summary.getByTestId('planned-waiting_seconds').textContent(),'0 s');
    assert.equal(await summary.getByTestId('planned-total_duration_seconds').textContent(),['completed-am','active-pm'].includes(mode)?'3160 s':'3227 s');
    const id=await summary.getByTestId('duration-route').textContent();
    assert.ok(id.includes(['completed-am','active-pm'].includes(mode)?'UI_PINNED_ROUTE':'UI_SAVED_ROUTE'));
   }
   for(const viewport of [{width:320,height:568},{width:390,height:844}]){
    await page.setViewportSize(viewport);
    const layout=await page.evaluate(()=>{
     const panel=document.querySelector('[aria-label="Database driver route"]');
     const header=panel.querySelector(':scope > header').getBoundingClientRect();
     const main=panel.querySelector(':scope > main');const bounds=main.getBoundingClientRect();
     return {headerBottom:header.bottom,mainTop:bounds.top,mainHeight:bounds.height,bottom:panel.getBoundingClientRect().bottom,
      width:document.documentElement.scrollWidth,viewport:innerWidth};
    });
    assert.ok(layout.mainTop>=layout.headerBottom-1,JSON.stringify(layout));
    assert.ok(layout.mainHeight>100,JSON.stringify(layout));
    assert.ok(layout.bottom<=viewport.height+1,JSON.stringify(layout));
    assert.ok(layout.width<=layout.viewport,JSON.stringify(layout));
   }
   if(mode==='active-pm'){
    await page.getByRole('heading',{name:'Persistent trip lifecycle',exact:true}).scrollIntoViewIfNeeded();
    assert.ok(await page.getByRole('heading',{name:'Persistent trip lifecycle',exact:true}).isVisible());
    const out=path.resolve(__dirname,'../node_modules/.cache/driver-duration-mobile.png');fs.mkdirSync(path.dirname(out),{recursive:true});
    await page.screenshot({path:out});
   }
   assert.equal(mutations,0);assert.deepEqual(errors,[]);passed.push(mode);
   await context.close();
  }
  console.log(JSON.stringify({passed,viewports:['320x568','390x844'],mutations:0,scope:'Intercepted synthetic UI and actual browser layout; no live provider calls'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
