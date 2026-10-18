// Intercepted UI contract test using the saved actual, unconfirmed scenario read.
// No real account credentials, writes to FastAPI, Google requests or fake ETAs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const initial=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
 const browser=await chromium.launch({headless:true});const checks=[],mutations=[],errors=[];
 try{
  const context=await browser.newContext();await context.addInitScript(()=>sessionStorage.setItem('saferide.login','isolated-ui-contract-only'));
  await context.route('**/*',async r=>{
   const u=new URL(r.request().url());const respond=(value,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
   if(u.pathname==='/api/auth/me')return respond({id:'UI_ONLY',username:'ui.test',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
   if(u.pathname==='/api/daily-plan'){
    const value=structuredClone(initial),day=u.searchParams.get('service_date');
    if(day!=='2026-10-19'){
     value.service_date=day;value.counts={morning:0,afternoon:0};
     for(const plan of Object.values(value.plans)){
      plan.route=null;plan.publication='not_generated';plan.publication_blockers=['Unknown dated attendance must be resolved.'];
      for(const row of plan.attendance.rows){row.am='unknown';row.pm='unknown';row.eligible=false;}
     }
    }
    return respond(value);
   }
   if(u.pathname==='/api/daily-plan/import'){mutations.push(r.request().postDataJSON());return respond({duplicate:false,changed:true,regenerated:[{status:'invalid_input'}]});}
   if(u.pathname==='/api/routing/vehicles')return respond([]);
   if(u.pathname.startsWith('/api/'))return respond({detail:'Unconfigured isolated UI endpoint'},503);
   return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort();
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://localhost:5173');
  await page.getByRole('button',{name:'Daily Plan',exact:true}).click();
  await page.getByText('Confirmed AM roster: 8 · Eligible provisional PM roster: 7',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('TEST_03 pm attendance',{exact:true}).inputValue(),'no');
  await page.getByText('SCH_A: Horizon College International',{exact:true}).waitFor();await page.getByText("SCH_B: Boys' Model College",{exact:true}).waitFor();
  checks.push('initial 8/7, correct school mapping, TEST_03 PM=no from actual stored scenario read');
  await page.getByRole('button',{name:"Boys' Model College — pending",exact:true}).click();
  assert.equal(await page.getByLabel('Latitude',{exact:true}).inputValue(),'6.903543');
  assert.equal(await page.getByRole('checkbox',{name:'I confirm this address and pin position are correct.'}).isChecked(),false);
  checks.push('user-supplied SCH_B pin retained and explicitly unconfirmed; no geocode call');
  await page.getByRole('button',{name:'Save dated attendance',exact:true}).click();
  await page.getByText('Input saved; routing is blocked or failed.',{exact:false}).waitFor();
  assert.equal(mutations.length,1);assert.equal(mutations[0].records.length,8);assert.equal(mutations[0].schema_version,'saferide-routing-provisional/v1');assert.equal(mutations[0].provenance,'landmark_test');
  checks.push('explicit attendance envelope; input saved/routing blocked distinguished');
  await page.getByLabel('Daily Plan service date',{exact:true}).fill('2026-10-20');
  await page.getByText('Confirmed AM roster: 0 · Eligible provisional PM roster: 0',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('TEST_03 pm attendance',{exact:true}).inputValue(),'unknown');
  checks.push('editable date; uninitialized day remains unknown, not copied attendance');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({checks,page_errors:errors,scope:'Intercepted UI test; actual scenario read fixture; no real mutations or external calls'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
