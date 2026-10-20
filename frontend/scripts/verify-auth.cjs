// Test credentials are ephemeral environment inputs from the rollback-only Python
// harness. Never use this file to store a local account password.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
let phase='initial';
(async()=>{
  const config=JSON.parse(process.env.SAFERIDE_AUTH_BROWSER_FIXTURE||'null');
  if(!config||!process.env.SAFERIDE_AUTH_BROWSER_PASSWORD)throw new Error('Use backend/verify_auth_browser.py; no credentials are stored in this script.');
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext();const errors=[];
    await context.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(url.pathname.startsWith('/api/')){
        const response=await route.fetch({url:config.base+url.pathname.slice(4)+url.search});
        await route.fulfill({response});
      }else if(['localhost','127.0.0.1'].includes(url.hostname))await route.continue();
      else await route.abort();
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.SAFERIDE_UI_TEST_URL||'http://localhost:5173');
    await page.getByRole('heading',{name:'SafeRide-LK login'}).waitFor();
    assert.equal(await page.getByRole('heading',{name:'Choose Interface'}).count(),0);
    async function login(role,mode='real'){
      await page.getByLabel('Username',{exact:true}).fill(config.users[role]);
      await page.getByLabel('Password',{exact:true}).fill(process.env.SAFERIDE_AUTH_BROWSER_PASSWORD);
      await page.getByLabel('Workspace').selectOption(mode);
      await page.getByRole('button',{name:'Sign in',exact:true}).click();
      await page.getByRole('button',{name:'Log out',exact:true}).waitFor();
    }
    async function logout(){await page.getByRole('button',{name:'Log out',exact:true}).click();await page.getByRole('heading',{name:'SafeRide-LK login'}).waitFor();}
    async function status(apiPath){return page.evaluate(async p=>{const response=await fetch('/api'+p,{headers:{Authorization:'Bearer '+sessionStorage.getItem('saferide.login')},credentials:'omit'});return response.status;},apiPath);}
    phase='driver login';await login('driverA');
    const panel=page.getByRole('region',{name:'Database driver route'});await panel.waitFor();
    phase='driver view';await panel.getByLabel('Driver test vehicle').locator(`option[value="${config.vehicles[0]}"]`).waitFor({state:'attached'});
    assert.equal(await panel.getByLabel('Driver test vehicle').locator(`option[value="${config.vehicles[1]}"]`).count(),0);
    assert.equal(await status('/routing/vehicles/'+config.vehicles[1]+'/positions'),403);
    phase='driver refresh';await page.reload();await panel.waitFor(); // Per-tab session survives refresh, trip stays in DB.
    phase='parent login';await logout();await login('parentA');
    await page.getByRole('heading',{name:'Your linked students'}).waitFor();
    const options=await page.getByLabel('Linked student',{exact:true}).locator('option').evaluateAll(nodes=>nodes.map(n=>n.value));
    assert.deepEqual(options,[config.students[0]]);
    assert.equal(await status('/parent/students/'+config.students[1]),403);
    assert.equal(await page.getByRole('heading',{name:'Choose Interface'}).count(),0);
    phase='admin login';await logout();await login('admin');await page.getByRole('button',{name:'Setup',exact:true}).click();await page.getByRole('button',{name:'Access',exact:true}).click();
    await page.getByRole('heading',{name:'Accounts and access',exact:true}).waitFor();
    phase='admin directory';await page.getByLabel('Manage account').locator('option').nth(1).waitFor({state:'attached'});
    phase='demo login';await logout();await login('admin','demo');
    await page.getByRole('heading',{name:'Choose Interface',exact:true}).waitFor();
    assert.equal(await status('/trips/'+config.trips[0]),403);
    phase='invalid session';await page.evaluate(()=>sessionStorage.setItem('saferide.login','sr_user_invalid'));
    await page.reload();await page.getByRole('heading',{name:'SafeRide-LK login'}).waitFor();
    assert.equal(await page.getByRole('heading',{name:'Choose Interface'}).count(),0);
    assert.deepEqual(errors,[]);
    const report={checks:['Anonymous sees login, no role bypass','Driver sees only assigned vehicle','Cross-vehicle history 403','Refresh preserves login','Parent sees only linked student','Cross-parent student 403','Real mode has no role selector','Admin access UI loads','Explicit authenticated demo has synthetic-only API scope','Invalid bearer returns login, never demo fallback'],page_errors:errors,fixture:'Rollback-only main.app backend; no paid APIs; no stored passwords'};
    fs.writeFileSync(path.resolve(__dirname,'../../docs/auth-browser-verification.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{await browser.close();}
})().catch(error=>{const safe=String(error.message).replaceAll(process.env.SAFERIDE_AUTH_BROWSER_PASSWORD||'not-a-password','[redacted]').replace(/sr_(?:user|track)_[A-Za-z0-9_-]+/g,'[redacted token]');console.error('Authentication browser check failed at '+phase+': '+safe.slice(0,1200));process.exitCode=1;});
