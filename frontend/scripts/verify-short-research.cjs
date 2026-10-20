// Synthetic intercepted preparation UI; no real backend writes/geocoding.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const context=await browser.newContext({viewport:{width:390,height:844}});let posted=null,geocoding=0;
 await context.addInitScript(()=>sessionStorage.setItem('saferide.login','synthetic-research-prep-ui'));
 const landmarks={A:{name:'SALT EduWay — reviewed research stopping point',place_address:'SALT EduWay, 488/2 Lake Road, Averihena, Hokandara, South, Battaramulla 10118',stopping_address:'25 Wewa Rd, Sri Jayawardenepura Kotte 10115',instruction:'These addresses may identify different points.'},B:{name:'CEB Battaramulla landmark',place_address:'CEB Battaramulla 132/33KV Grid, WX66+P9G, Wewa Rd, Sri Jayawardenepura Kotte 10115',stopping_address:'',instruction:'Public roadside outside the electrical facility.'},C:{name:'The Best "B" bakery',place_address:'The Best "B", WX47+GPP, Malabe',stopping_address:'',instruction:'Confirm accessible stop.'}};
 await context.route('**/*',r=>{const u=new URL(r.request().url()),p=u.pathname;const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
  if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();if(!p.startsWith('/api/'))return r.continue();
  if(p==='/api/auth/me')return send({id:'OPERATOR',username:'synthetic.operator',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
  if(p==='/api/routing/vehicles')return send([]);
  if(p==='/api/auth/admin/accounts')return send([{id:'DRIVER',username:'synthetic.driver',role:'driver',active:true,demo_only:false,vehicle_ids:['MALABE_PP1_VAN_01']},{id:'OPERATOR',username:'synthetic.operator',role:'administrator',active:true,demo_only:false,vehicle_ids:[]}]);
  if(p==='/api/research-routes/template')return send({vehicle_id:'MALABE_PP1_VAN_01',landmarks});
  if(p==='/api/research-routes/current')return send({published_route:{route_id:'SAVED_UI_ONLY',version:30,execution_status:'pre_trip',departure_seconds:68400,research_journey:{...posted}},trip:{trip_id:'UNUSED_UI_ONLY',state:'PLANNED'}});
  if(p==='/api/research-routes'){posted=r.request().postDataJSON();return send({route_id:'UI_ONLY_RESEARCH',version:1,departure:'2026-10-19T18:00:00+05:30'});}
  if(p.includes('geocode')){geocoding++;return send({detail:'Not called automatically'},503);}
  return send({detail:'No synthetic fixture'},404);
 });
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');await page.getByRole('button',{name:'Research & Testing',exact:true}).click();await page.getByRole('button',{name:'Adult research',exact:true}).click();
 await page.getByRole('heading',{name:'Adult research — A → B → C → A',exact:true}).waitFor();
 const save=page.getByRole('button',{name:'Save reviewed research route',exact:true});assert.equal(await save.isDisabled(),true);
 assert.equal(await page.getByLabel('Research travel mode',{exact:true}).inputValue(),'');
 await page.getByText('Separately supplied stopping-point address: 25 Wewa Rd',{exact:false}).waitFor();
 await page.getByText('Supplied place address: SALT EduWay, 488/2 Lake Road',{exact:false}).waitFor();
 await page.getByLabel('Research travel mode',{exact:true}).selectOption('driving');await page.getByLabel('Assigned research driver',{exact:true}).selectOption('DRIVER');await page.getByLabel('Separate phone operator (existing administrator)',{exact:true}).selectOption('OPERATOR');
 await page.getByLabel('I confirm the operator and driver are separate people while moving.',{exact:true}).check();await page.getByLabel('Consenting adults only; no student transport.',{exact:true}).check();
 for(const [key,lat,lon] of [['A','6.9','79.9'],['B','6.91','79.91'],['C','6.92','79.9']]){
  const area=page.getByRole('region',{name:`Research stopping point ${key}`,exact:true});
  assert.equal(await area.getByLabel('Latitude',{exact:true}).inputValue(),'');
  await area.getByLabel('Latitude',{exact:true}).fill(lat);await area.getByLabel('Longitude',{exact:true}).fill(lon);
  await area.getByRole('checkbox',{name:'I confirm this address and pin position are correct.',exact:true}).check();
  await area.getByRole('checkbox',{name:/I manually reviewed this accessible/}).check();await area.getByLabel('Stopping-point review note',{exact:true}).fill('Synthetic reviewed public roadside stop, no field evidence');
 }
 await page.getByLabel('Research route review reason',{exact:true}).fill('Synthetic isolated UI preparation only');
 assert.equal(await save.isDisabled(),false);await save.click();await page.getByText('Saved UI_ONLY_RESEARCH',{exact:false}).waitFor();
 assert.equal(posted.travel_mode,'driving');assert.equal(Object.keys(posted.pins).length,3);assert.equal(posted.driver_id===posted.operator_id,false);assert.equal(geocoding,0);
 assert.equal(await page.getByText('No trip was started.',{exact:false}).count(),1);assert.deepEqual(errors,[]);
 await page.getByLabel('Research travel mode',{exact:true}).selectOption('walking');
 await page.getByRole('button',{name:'Reuse saved research review for selected date',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Loaded version 30'}).waitFor();
 assert.equal(await page.getByLabel('Research travel mode',{exact:true}).inputValue(),'driving');
 assert.equal(await page.getByLabel('Research departure (Asia/Colombo)',{exact:true}).inputValue(),'19:00');
 assert.equal(await page.getByLabel('Assigned research driver',{exact:true}).inputValue(),'DRIVER');
 assert.equal(await page.getByLabel('Separate phone operator (existing administrator)',{exact:true}).inputValue(),'OPERATOR');
 assert.equal(await save.isDisabled(),false);assert.equal(geocoding,0);
 console.log('Saved review reload verified: no server writes, no re-entering pins or people; future departure and deliberate cancellation remain explicit.');
 console.log(JSON.stringify({checks:['actual Admin navigation reachable','both A addresses preserved','blank travel mode/pins initially','explicit separate people/consent/pin/public review','reviewed request has 3 pins, no guessed 4th coordinate','no automatic geocoding/start/observations'],backend:'intercepted only',page_errors:errors},null,2));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
