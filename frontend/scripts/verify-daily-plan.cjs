// Intercepted UI contract test using the saved actual, unconfirmed scenario read.
// No real account credentials, writes to FastAPI, Google requests or fake ETAs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const initial=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
 const browser=await chromium.launch({headless:true});const checks=[],mutations=[],errors=[],generations=[];
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
   if(u.pathname==='/api/daily-plan/import'){
    const body=r.request().postDataJSON();const duplicate=mutations.some(m=>m.event_id===body.event_id);mutations.push(body);
    if(body.kind==='assignment'&&body.geocoding_http_budget===1){
     initial.location_imports=[{external_id:'TEST_01',event_id:body.event_id,status:'ambiguous',supplied_address:body.records[0].address,result_source:'live_provider',current_location_confirmed:false,provider_result:{formatted_address:'Intercepted building suggestion',candidate_count:2,partial_match:true},note:'Synthetic UI fixture; stopping point review required.'}];
     return respond({duplicate,geocoding_counts:{attempted:duplicate?0:1,ambiguous:duplicate?0:1},regenerated:[{status:'invalid_input'}]});
    }
    if(body.kind==='boarding'&&body.records[0].direction==='afternoon')return respond({duplicate,event_id:body.event_id,boarding_result:{status:body.records[0].resolves_event_id?'delayed_evidence_resolved':'test_boarding_confirmed',outcome_state:'PICKED_UP'},regenerated:[]});
    return respond({duplicate:false,changed:true,regenerated:[{status:'invalid_input'}]});
   }
   if(u.pathname==='/api/daily-plan/generate'){
    const body=r.request().postDataJSON();generations.push(body);
    initial.plans.morning.route.departure_recommendation={mode:body.departure_mode,status:'search_incomplete',recommended_departure_seconds:null,preferred_feasible:null,hard_feasible:null,estimate_timestamp:'2026-10-18T10:00:00Z',assumptions:['Isolated intercepted UI failure fixture; no provider estimates.']};
    return respond(initial.plans.morning.route);
   }
   if(u.pathname==='/api/routing/vehicles')return respond([]);
   if(u.pathname.startsWith('/api/'))return respond({detail:'Unconfigured isolated UI endpoint'},503);
   return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort();
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://localhost:5173');
  await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByText('Administrator tools',{exact:true}).click();await page.getByRole('button',{name:'School test tools',exact:true}).click();await page.getByLabel('Daily Plan service date',{exact:true}).fill('2026-10-19');await page.getByText('Review stopping locations',{exact:true}).click();
  await page.getByRole('region',{name:'Daily transport summary'}).getByText('8',{exact:true}).waitFor();assert.equal(await page.getByRole('region',{name:'Daily transport summary'}).getByText('7',{exact:true}).count(),1);
  assert.equal(await page.getByLabel('TEST_03 pm attendance',{exact:true}).inputValue(),'no');
  await page.getByRole('region',{name:'Daily transport summary'}).getByText(/Schools:.*Horizon College International/).waitFor();
  checks.push('initial 8/7, correct school mapping, TEST_03 PM=no from actual stored scenario read');
  await page.getByRole('button',{name:"Boys' Model College — pending",exact:true}).click();
  assert.equal(await page.getByLabel('Latitude',{exact:true}).inputValue(),'6.903543');
  assert.equal(await page.getByRole('checkbox',{name:'I confirm this address and pin position are correct.'}).isChecked(),false);
  checks.push('user-supplied SCH_B pin retained and explicitly unconfirmed; no geocode call');
  await page.getByRole('button',{name:'Save dated attendance',exact:true}).click();
  await page.getByText('Input saved; routing is blocked or failed.',{exact:false}).waitFor();
  assert.equal(mutations.length,1);assert.equal(mutations[0].records.length,8);assert.equal(mutations[0].schema_version,'saferide-routing-provisional/v1');assert.equal(mutations[0].provenance,'landmark_test');
  checks.push('explicit attendance envelope; input saved/routing blocked distinguished');
  await page.getByRole('button',{name:'Recommend AM departure',exact:true}).click();
  await page.getByText('Recommendation: search_incomplete',{exact:false}).waitFor();
  assert.equal(generations[0].departure_mode,'recommend');assert.equal(generations[0].provider,'simulation');
  await page.getByLabel('Daily Plan provider',{exact:true}).selectOption('google');
  assert.equal(await page.getByRole('button',{name:'Recommend AM departure',exact:true}).isDisabled(),true);
  await page.getByText('Recommendation request budget',{exact:true}).click();await page.getByText('Google request approval and limits',{exact:true}).click();await page.getByLabel('Recommendation live budget',{exact:true}).fill('1');
  await page.getByLabel('Traffic fallback policy',{exact:true}).selectOption('ml');
  assert.equal(await page.getByRole('button',{name:'Recommend AM departure',exact:true}).isDisabled(),false);
  await page.getByRole('button',{name:'Recommend AM departure',exact:true}).click();
  await page.getByText('Departure search saved; inspect recommendation status and current version.',{exact:true}).waitFor();
  assert.equal(generations[1].recommendation_live_budget,1);
  assert.equal(generations[1].fallback_policy,'ml');
  await page.getByText('Recommended departure: Unavailable',{exact:false}).waitFor();
  await page.getByText('Selected saved departure: No feasible departure selected',{exact:true}).waitFor();
  checks.push('recommendation request, incomplete status, Google explicit zero-default budget; all intercepted');
  await page.getByLabel('Daily Plan provider',{exact:true}).selectOption('simulation');
  await page.getByLabel('AM departure',{exact:true}).fill('06:30');
  await page.getByRole('button',{name:'Validate AM override',exact:true}).click();
  await page.getByText('Saved route generation completed; inspect actual status below.',{exact:true}).waitFor();
  assert.equal(generations[2].departure_mode,'override');assert.equal(generations[2].departure_seconds,23400);
  checks.push('administrator override submits supplied time for backend revalidation, not client-calculated feasibility');
  await page.getByLabel('Daily Plan provider',{exact:true}).selectOption('google');
  assert.equal(await page.getByRole('button',{name:'Validate AM override',exact:true}).isDisabled(),true);
  await page.getByText('Google request approval and limits',{exact:true}).click();await page.getByLabel('Traffic verification HTTP budget',{exact:true}).fill('1');
  assert.equal(await page.getByRole('button',{name:'Validate AM override',exact:true}).isDisabled(),false);
  await page.getByLabel('Traffic verification HTTP budget',{exact:true}).fill('0');
  await page.getByLabel('Controlled traffic adapter failure',{exact:true}).check();
  await page.getByLabel('Request ordered Google road geometry',{exact:true}).check();
  await page.getByText('TEST injection enabled.',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Recommend AM departure',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Validate AM override',exact:true}).click();
  await page.getByText('Saved route generation completed; inspect actual status below.',{exact:true}).waitFor();
  assert.equal(generations[3].force_live_failure,true);assert.equal(generations[3].live_http_budget,0);assert.equal(generations[3].fallback_policy,'ml');
  assert.equal(generations[3].include_geometry,true);
  checks.push('admin traffic HTTP opt-in, visible controlled test, declared ML policy and disabled live recommendation during injection; intercepted only');
  await page.getByLabel('PM boarding test trip ID',{exact:true}).fill('UI_ONLY_ISOLATED_PM');
  await page.getByLabel('PM boarding test event ID',{exact:true}).fill('UI_PM_EVENT_1');
  await page.getByLabel('PM boarding test event time',{exact:true}).fill('2026-10-19T13:35:00+05:30');
  await page.getByRole('button',{name:'Record manual PM boarding test event',exact:true}).click();
  await page.getByText('UI_PM_EVENT_1: test_boarding_confirmed',{exact:false}).waitFor();
  const pm=mutations.at(-1);assert.equal(pm.producer,'manual_test');assert.equal(pm.provenance,'landmark_test');assert.equal(pm.records[0].trip_id,'UI_ONLY_ISOLATED_PM');assert.equal(pm.records[0].direction,'afternoon');assert.equal(pm.occurred_at,'2026-10-19T13:35:00+05:30');
  await page.getByRole('button',{name:'Record manual PM boarding test event',exact:true}).click();
  await page.getByText('UI_PM_EVENT_1: Duplicate event',{exact:false}).waitFor();
  await page.getByLabel('PM boarding test event ID',{exact:true}).fill('UI_PM_REVIEW_1');
  await page.getByLabel('PM boarding resolution event ID',{exact:true}).fill('UI_PM_EVENT_1');
  await page.getByLabel('PM boarding test event time',{exact:true}).fill('2026-10-19T13:47:00+05:30');
  await page.getByRole('button',{name:'Record manual PM boarding test event',exact:true}).click();
  await page.getByText('UI_PM_REVIEW_1: delayed_evidence_resolved',{exact:false}).waitFor();
  assert.equal(mutations.at(-1).records[0].resolves_event_id,'UI_PM_EVENT_1');
  checks.push('manual PM test provenance, stable duplicate event ID and explicit delayed-evidence review; intercepted only');
  await page.getByText('Provisional registration/address import',{exact:true}).click();
  const registration={schema_version:'saferide-routing-provisional/v1',event_id:'INTERCEPTED_REGISTRATION_1',occurred_at:new Date().toISOString(),producer:'hasara_adapter_provisional',provenance:'landmark_test',kind:'assignment',reason:'Intercepted registration only',geocoding_http_budget:1,records:[{student_external_id:'TEST_01',school_external_id:'SCH_A',address:'  Supplied synthetic address unchanged  '}]};
  await page.getByLabel('Provisional registration event JSON',{exact:true}).fill(JSON.stringify(registration));
  await page.getByRole('button',{name:'Import provisional registration/address event',exact:true}).click();
  await page.getByText('Review stopping locations',{exact:true}).click();await page.getByText('TEST_01: ambiguous / live_provider / Vehicle stopping point review required',{exact:true}).waitFor();
  assert.equal(mutations.at(-1).records[0].address,registration.records[0].address);
  await page.getByText('Provisional registration/address import',{exact:true}).click();
  await page.getByRole('button',{name:'Import provisional registration/address event',exact:true}).click();
  await page.getByText('Duplicate: original results retained; no repeat lookup.',{exact:false}).waitFor();
  assert.equal(mutations.at(-1).event_id,registration.event_id);
  checks.push('provisional registration JSON preserves supplied address/event ID; ambiguous result and duplicate status shown; intercepted only');
  await page.getByLabel('Daily Plan service date',{exact:true}).fill('2026-10-20');
  await page.getByRole('region',{name:'Daily transport summary'}).getByText('0',{exact:true}).first().waitFor();assert.equal(await page.getByRole('region',{name:'Daily transport summary'}).getByText('0',{exact:true}).count(),2);
  assert.equal(await page.getByLabel('TEST_03 pm attendance',{exact:true}).inputValue(),'unknown');
  checks.push('editable date; uninitialized day remains unknown, not copied attendance');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({checks,page_errors:errors,scope:'Intercepted UI test; actual scenario read fixture; no real mutations or external calls'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
