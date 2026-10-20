// Browser geolocation and upload responses are intercepted synthetic fixtures.
// No real-device verification claim, persisted positions or paid external calls.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});const checks=[];
 async function setup(mode){
  const page=await browser.newPage();const uploads=[];let clears=0;
  await page.route('**/*',r=>{
   const u=new URL(r.request().url());
   if(u.pathname==='/api/tracking/positions'){
    const sample=r.request().postDataJSON();uploads.push(sample);
    const status=mode==='revoked'?401:mode==='retry'&&uploads.length===1?503:200;
    return r.fulfill({status,contentType:'application/json',body:JSON.stringify(status!==200?{detail:'Controlled upload rejection'}:{sample:{...sample,id:'UI_POSITION',source:'actual_device',tracking_session_id:'UI_SESSION',received_at:new Date().toISOString(),accuracy_quality:sample.accuracy_m>50?'poor':'acceptable'},duplicate:false})});
   }
   if(u.pathname.startsWith('/api/'))return r.fulfill({status:401,body:'{}'});
   return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort();
  });
  await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');
  await page.evaluate(async mode=>{
   Object.defineProperty(navigator,'geolocation',{configurable:true,value:{watchPosition(ok,fail){window.phoneOk=ok;window.phoneFail=fail;return 1;},clearWatch(){window.phoneClears=(window.phoneClears||0)+1;}}});
   if(mode==='offline')Object.defineProperty(navigator,'onLine',{configurable:true,value:false});
   const R=await import('/node_modules/.vite/deps/react.js'),D=await import('/node_modules/.vite/deps/react-dom_client.js'),C=await import('/src/components/PhoneGpsCapture.tsx');
   const host=document.createElement('div');document.body.append(host);
   window.phoneRoot=(D.createRoot||D.default.createRoot)(host);
   window.phoneRoot.render(R.default.createElement(C.PhoneGpsCapture,{credential:'isolated-ui-test-only',expiresAt:new Date(Date.now()+3600000).toISOString()}));
  },mode);
  await page.getByRole('button',{name:'Start sharing',exact:true}).click();
  await page.waitForFunction(()=>!!window.phoneOk);
  return {page,uploads};
 }
 async function emit(page,accuracy=8){await page.evaluate(accuracy=>window.phoneOk({timestamp:Date.now(),coords:{latitude:6.9,longitude:79.9,accuracy,speed:null}}),accuracy);}
 try{
  {
   const {page,uploads}=await setup('normal');await emit(page);
   await page.getByText('Sharing — upload accepted',{exact:false}).waitFor();
   assert.equal(uploads.length,1);assert.equal(uploads[0].speed_mps,null);assert.equal(uploads[0].accuracy_m,8);
   assert.equal('vehicle_id' in uploads[0],false);assert.equal('source' in uploads[0],false);assert.equal('trip_id' in uploads[0],false);
   assert.ok(uploads[0].sample_id);assert.ok(uploads[0].recorded_at);
   await page.getByRole('button',{name:'Stop sharing',exact:true}).click();
   await page.getByText('Stopped; pending samples discarded',{exact:false}).waitFor();
   assert.ok(await page.evaluate(()=>window.phoneClears)>0);
   checks.push('opt-in capture; nullable speed; accuracy/timestamp/sample ID; no forged binding fields; stop clears watch');await page.close();
  }
  {
   const {page,uploads}=await setup('retry');await emit(page);
   await page.getByText('Sharing — upload accepted',{exact:false}).waitFor();
   assert.equal(uploads.length,2);assert.deepEqual(uploads[0],uploads[1]);checks.push('transient failure retries the same immutable sample');await page.close();
  }
  {
   const {page,uploads}=await setup('revoked');await emit(page);
   await page.getByText('Authorization or trip rejected — sharing stopped',{exact:false}).waitFor();
   assert.equal(uploads.length,1);checks.push('revoked authorization stops capture and clears queue');await page.close();
  }
  {
   const {page,uploads}=await setup('offline');
   await page.evaluate(()=>{for(let i=0;i<35;i++)window.phoneOk({timestamp:Date.now()+i*5000,coords:{latitude:6.9,longitude:79.9,accuracy:9,speed:null}});});
   await page.getByText('Queued: 30 / 30',{exact:false}).waitFor();assert.equal(uploads.length,0);
   await page.getByRole('button',{name:'Stop sharing',exact:true}).click();await page.getByText('Queued: 0 / 30',{exact:false}).waitFor();
   checks.push('offline queue bounded to 30; stop discards queued samples');await page.close();
  }
  {
   const {page,uploads}=await setup('permission');await page.evaluate(()=>window.phoneFail({code:1}));
   await page.getByText('Sharing state: Permission denied',{exact:true}).waitFor();assert.equal(uploads.length,0);
   checks.push('permission denied visible; no invented upload');await page.close();
  }
  console.log(JSON.stringify({checks,scope:'Synthetic browser fixtures; actual Android ingestion still requires a phone and eligible trip'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
