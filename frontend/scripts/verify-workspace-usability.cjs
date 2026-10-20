// Intercepted synthetic UI only: no backend writes, exports of real data or paid calls.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844}});
  await context.addInitScript(()=>sessionStorage.setItem('saferide.login','synthetic-usability-test'));
  const day=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
  let writes=[],fail=false,downloads=0;const errors=[];
  const observation={id:'UI_OBSERVATION',revision:2,status:'accepted',dataset:'moving_adult_landmark',raw:{trip_id:'UI_TRIP',origin_sequence:2,destination_sequence:3,departure_position_id:'UI_EXIT',arrival_position_id:'UI_ENTRY',dwell_reviewed:true,intervals:[],reason:'Prior synthetic review'},analysis:{flags:[],elapsed_duration_s:null,duration_s:null,origin_id:'UI_B',destination_id:'UI_C'}};
  await context.route('**/*',async r=>{
   const u=new URL(r.request().url()),p=u.pathname;
   const send=(v,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(v)});
   if(!['localhost','127.0.0.1'].includes(u.hostname))return r.abort();
   if(!p.startsWith('/api/'))return r.continue();
   if(p==='/api/auth/me')return send({id:'UI_ADMIN',username:'synthetic.admin',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
   if(p==='/api/daily-plan')return send(day);
   if(p==='/api/routing/vehicles')return send([]);
   if(p==='/api/research/evaluation')return send({candidate_segments:1,accepted:1,rejected:0,pending:0,sources:{moving_adult_landmark:1},flag_counts:{},rejection_reasons:{},truncated:false});
   if(p==='/api/research/observations')return send({observations:[observation]});
   if(p==='/api/research/observations/UI_OBSERVATION/review'){
    writes.push(r.request().postDataJSON());await new Promise(resolve=>setTimeout(resolve,250));
    return fail?send({detail:'Controlled review save unavailable'},503):send({id:'UI_REVISION'});
   }
   if(p==='/api/research/export'){downloads++;return send({observations:[],note:'Synthetic intercepted export, no real observations'});}
   return send({detail:'Synthetic endpoint unavailable'},503);
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');
  if(page.viewportSize().width<768)await page.getByRole('button',{name:'Open navigation',exact:true}).click();await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByText('Administrator tools',{exact:true}).click();await page.getByRole('button',{name:'Evaluation',exact:true}).click();
  const section=page.getByRole('region',{name:'Travel-time Evaluation',exact:true});
  await section.getByText('Missing prerequisite: enter the research trip ID to load, prepare or export.',{exact:true}).waitFor();
  await section.getByLabel('Research trip ID',{exact:true}).fill('UI_TRIP');
  await section.getByRole('button',{name:'Refresh evaluation',exact:true}).click();
  const review=section.getByRole('button',{name:'Review / correct segment',exact:true});await review.waitFor();
  const editor=section.locator('details').first();
  assert.equal(await editor.getAttribute('open'),null);
  await review.click();
  const heading=section.getByRole('heading',{name:'Reviewing observation UI_OBSERVATION',exact:true});
  await heading.waitFor();assert.equal(await heading.evaluate(el=>el===document.activeElement),true);
  assert.equal(await section.getByLabel('Origin stop sequence',{exact:true}).inputValue(),'2');
  assert.equal(await section.getByLabel('Departure boundary position ID',{exact:true}).inputValue(),'UI_EXIT');
  await section.getByRole('button',{name:'Add observed interval',exact:true}).click();
  await section.getByText('Interval requires valid start/end',{exact:false}).waitFor();assert.equal(writes.length,0);
  await section.getByLabel('Interval start',{exact:true}).fill('2026-10-19T18:05:00+05:30');
  await section.getByLabel('Interval end',{exact:true}).fill('2026-10-19T18:06:00+05:30');
  await section.getByLabel('Interval reason',{exact:true}).fill('Synthetic observed pause');
  await section.getByRole('button',{name:'Add observed interval',exact:true}).click();
  await section.getByRole('button',{name:'Remove interval 1',exact:true}).waitFor();
  const raw=section.getByLabel('Known dwell intervals',{exact:true});assert.equal(await raw.isVisible(),false);
  await section.getByLabel('Research review reason',{exact:true}).fill('Synthetic corrected boundary review');
  await section.getByLabel('Review decision',{exact:true}).selectOption('pending');
  const save=section.getByRole('button',{name:'Save review revision',exact:true});
  await save.evaluate(el=>{el.click();el.click();});
  await section.getByText('Observation revision saved',{exact:false}).waitFor();
  assert.equal(writes.length,1);assert.equal(writes[0].intervals[0].kind,'dwell');assert.equal(writes[0].status,'pending');
  await review.click();await section.getByLabel('Research review reason',{exact:true}).fill('Synthetic failed revision remains editable');fail=true;await save.click();
  await section.getByText('Controlled review save unavailable',{exact:false}).waitFor();
  assert.equal(await save.isVisible(),true);assert.equal(writes.length,2);
  await section.getByRole('button',{name:'Download reviewed research export',exact:true}).click();assert.equal(downloads,1);
  for(const viewport of [{width:1366,height:900},{width:320,height:568},{width:390,height:844}]){
   await page.setViewportSize(viewport);await heading.scrollIntoViewIfNeeded();
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),JSON.stringify(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&e.getBoundingClientRect().width>0).filter(e=>!(()=>{for(let a=e.parentElement;a&&a!==document.body;a=a.parentElement){if(['auto','hidden','scroll'].includes(getComputedStyle(a).overflowX))return true;}return false;})()).slice(0,20).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,65),right:e.getBoundingClientRect().right}))}))));
  }
  fs.mkdirSync(path.resolve(__dirname,'../node_modules/.cache'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../node_modules/.cache/workspace-usability-mobile.png')});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({checks:['missing prerequisites','review opens and focuses selected revision','structured offset-aware dwell fields; raw JSON collapsed','invalid interval rejected locally','rapid duplicate submit sends one request','success and error feedback; failed editor retained','reviewed export request','1366/320/390 px no horizontal page overflow'],page_errors:errors,scope:'synthetic intercepted requests only'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
