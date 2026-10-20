// Intercepted UI only. No Google API, credentials or operational writes.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const fixture=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
 const route=fixture.plans.morning.route;
 Object.assign(route,{feasibility_status:'feasible',is_current:true,road_geometry:{status:'available',map_available:true,description:'Synthetic intercepted geometry fixture; no live road claim.'}});
 let images=0;
 const context=await browser.newContext({viewport:{width:390,height:844}});
 await context.addInitScript(()=>sessionStorage.setItem('saferide.login','intercepted-road-test'));
 await context.route('**/*',request=>{
  const u=new URL(request.request().url());
  if(!['127.0.0.1','localhost'].includes(u.hostname))return request.abort();
  if(!u.pathname.startsWith('/api/'))return request.continue();
  const send=v=>request.fulfill({contentType:'application/json',body:JSON.stringify(v)});
  if(u.pathname==='/api/auth/me')return send({id:'UI_ONLY',username:'intercepted.admin',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
  if(u.pathname==='/api/routing/notifications')return send({notifications:[],unread_count:0});
  if(u.pathname==='/api/daily-plan')return send(fixture);
  if(u.pathname.endsWith('/map-image')){images++;return request.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9S8AAAAASUVORK5CYII=','base64')});}
  return send([]);
 });
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const open=async()=>{await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');await page.getByRole('button',{name:'Open navigation',exact:true}).click();await page.getByRole('button',{name:'Daily Plan',exact:true}).click();await page.getByRole('button',{name:'Open AM route',exact:true}).click();await page.getByRole('button',{name:'Load Google road map (up to 1 image request)',exact:true}).waitFor();};
 await open();assert.equal(images,0);
 await page.getByRole('button',{name:'Load Google road map (up to 1 image request)',exact:true}).click();
 const img=page.getByAltText('Ordered road geometry on a Google Map');await img.waitFor();
 assert.equal(images,1);assert.match(await img.getAttribute('src'),/^blob:/);
 assert.equal(await img.evaluate(node=>new Promise(resolve=>{if(node.complete)return resolve(node.naturalWidth>0);node.onload=()=>resolve(node.naturalWidth>0);node.onerror=()=>resolve(false);})),true);
 await page.getByRole('button',{name:'View confirmed locations',exact:true}).click();await page.getByRole('dialog',{name:'Confirmed locations',exact:true}).waitFor();assert.equal(await page.locator('details').count(),0);await open();assert.equal(images,1);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({checks:['no image request on page load','explicit click issues one authorized image request','blob image renders at mobile viewport','page reload does not auto-request','no page errors'],scope:'intercepted synthetic PNG, not a live Google browser screenshot'},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
