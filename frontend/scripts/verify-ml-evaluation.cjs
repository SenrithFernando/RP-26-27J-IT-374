// Saved synthetic metrics and intercepted UI; no training, Google or DB writes.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const initial=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/malabe-initial-plan.json'),'utf8'));
 const report=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/ml_metrics.json'),'utf8'));
 let available=true;const context=await browser.newContext({viewport:{width:390,height:844}});
 await context.addInitScript(()=>sessionStorage.setItem('saferide.login','intercepted-ml-ui'));
 await context.route('**/*',request=>{
  const u=new URL(request.request().url());if(!['localhost','127.0.0.1'].includes(u.hostname))return request.abort();
  if(!u.pathname.startsWith('/api/'))return request.continue();
  const send=(value,status=200)=>request.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
  if(u.pathname==='/api/auth/me')return send({id:'UI_ONLY',username:'fixture.admin',role:'administrator',mode:'real',expires_at:new Date(Date.now()+3600000).toISOString(),vehicle_ids:[],student_ids:[]});
  if(u.pathname==='/api/ml/status')return send({available,model_version:available?report.model_version:null,training_data_source:available?'synthetic':null,reason:available?null:'Isolated missing-model fixture',feature_schema:available?report.feature_schema:null,evaluation:available?report:null});
  if(u.pathname==='/api/daily-plan'){
   const day=structuredClone(initial),route=day.plans.morning.route;
   route.feasibility_status=available?'feasible':'unavailable';route.is_current=available;route.provider_source={requested_provider:'google',duration_source:available?'ml_prediction':'unavailable',model_version:available?report.model_version:null,fallback_reasons:[available?'Forced live adapter failure; loaded ML used.':'Model unavailable; no prediction.'],force_live_failure:true,live_http_requests:0};
   return send(day);
  }
  return send({detail:'Isolated endpoint unavailable'},404);
 });
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function open(){await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://127.0.0.1:5187');if(page.viewportSize().width<768)await page.getByRole('button',{name:'Open navigation',exact:true}).click();await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByText('Administrator tools',{exact:true}).click();await page.getByRole('button',{name:'Evaluation',exact:true}).click();await page.getByText('Synthetic-trained ML evaluation',{exact:true}).click();}
 await open();await page.getByText('Samples: 2000 total / 1500 development / 500 untouched final test; 400 synthetic trips.',{exact:true}).waitFor();
 await page.getByRole('cell',{name:'28.013 / 0.467',exact:true}).waitFor();await page.getByRole('cell',{name:'57.087 / 0.951',exact:true}).waitFor();
 await page.getByText('Chronological folds and prediction-time feature schema',{exact:true}).click();await page.getByText(/Fold 4: train 1250/).waitFor();
 await page.getByRole('button',{name:'School test tools',exact:true}).click();await page.getByText('Provider details and request usage',{exact:true}).first().click();
 await page.getByText(/Requested: google.*Actual route source: ml_prediction/).waitFor();
 await page.getByText('Fallback/unavailable reason: Forced live adapter failure; loaded ML used.',{exact:true}).waitFor();
 available=false;await open();await page.getByText('Model unavailable: Isolated missing-model fixture',{exact:true}).waitFor();
 assert.equal(await page.getByRole('cell',{name:'28.013 / 0.467',exact:true}).count(),0);
 await page.getByRole('button',{name:'School test tools',exact:true}).click();await page.getByText('Provider details and request usage',{exact:true}).first().click();
 await page.getByText(/Requested: google.*Actual route source: Unavailable/).waitFor();assert.deepEqual(errors,[]);
 console.log(JSON.stringify({checks:['saved synthetic metrics/counts/baseline visible','chronological ranges and schema expandable','Google request accurately labelled ML fallback with model version/reason','unavailable model has no fabricated metrics or predictions','mobile viewport and no page errors'],scope:'intercepted synthetic UI only; no paid calls'},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
