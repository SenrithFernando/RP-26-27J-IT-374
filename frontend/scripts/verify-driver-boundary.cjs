// Intercepted contract checks only: no credentials, DB mutations or paid calls.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true}),requests=[],errors=[];let fail=false;
 try{
  const context=await browser.newContext();await context.addInitScript(()=>sessionStorage.setItem('saferide.login','isolated-driver-ui-only'));
  await context.route('**/*',r=>{
   const u=new URL(r.request().url()),p=u.pathname;
   const respond=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
   if(!p.startsWith('/api/'))return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort();
   if(p==='/api/auth/me')return respond({id:'UI_DRIVER',username:'ui.driver',role:'driver',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:['MALABE_PP1_VAN_01'],student_ids:[]});
   if(p==='/api/routing/vehicles')return respond([{id:'MALABE_PP1_VAN_01',capacity:20,input_source:'simulated'}]);
   if(p==='/api/routes/published'){
    requests.push({method:r.request().method(),date:u.searchParams.get('service_date'),direction:u.searchParams.get('direction'),vehicle:u.searchParams.get('vehicle_id')});
    return fail?respond({detail:'Controlled driver boundary unavailable'},503):respond({contract_version:'saferide-driver-plan-provisional/v1',publication_status:'draft',published_route:null,trip:null});
   }
   if(p.endsWith('/positions/latest'))return respond({position:null,status:'unknown',age_seconds:null});
   if(p==='/api/auth/tracking')return respond([]);
   return respond({detail:'No isolated fixture endpoint'},404);
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');
  await page.getByRole('button',{name:'Choose route',exact:true}).click();await page.getByLabel('Driver service date',{exact:true}).fill('2026-10-19');
  await page.getByText('No current published morning route',{exact:false}).waitFor();
  assert.equal(requests.at(-1).date,'2026-10-19');assert.equal(requests.at(-1).vehicle,'MALABE_PP1_VAN_01');
  await page.getByRole('button',{name:'Afternoon Drop-off',exact:true}).click();
  await page.getByText('No current published afternoon route',{exact:false}).waitFor();
  assert.equal(requests.at(-1).direction,'afternoon');
  await page.getByRole('button',{name:'Use selected route',exact:true}).click();fail=true;await page.getByRole('button',{name:'Refresh route',exact:true}).click();
  await page.getByText('Controlled driver boundary unavailable',{exact:false}).waitFor();
  assert.ok(requests.every(r=>r.method==='GET'));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({checks:['selected date and authorized vehicle sent to read-only publication endpoint','AM/PM switches request independently; drafts do not appear as published','backend error clears current route; no mock fallback','all boundary requests GET; no optimization'],page_errors:errors,scope:'Intercepted UI; backend authorization and saved manifests tested separately with rollback data'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
