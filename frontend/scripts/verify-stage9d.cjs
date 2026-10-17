// Real stored events; fixture read-state writes only. No SMS/push or paid provider calls.
const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
  const file=path.resolve(__dirname,'../../docs/stage9d_verification.json');const report=JSON.parse(fs.readFileSync(file,'utf8'));
  assert(report.missed_student_id.startsWith('S9D_'),'Only isolated notification fixtures allowed.');
  const base='http://127.0.0.1:8000';
  async function readState(recipient,read){const r=await fetch(`${base}/routing/notifications/${report.notification_id}/read`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient,...(recipient==='parent'?{student_id:report.missed_student_id}:{}),read})});assert(r.ok);return r.json();}
  await readState('admin',false);await readState('parent',false);
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1100}});const errors=[];
    await context.route('**://tile.openstreetmap.org/**',r=>r.abort());
    const admin=await context.newPage();admin.on('pageerror',e=>errors.push(e.message));await admin.goto('http://127.0.0.1:5173');
    await admin.getByRole('button',{name:'Administrator',exact:true}).click();await admin.locator('nav').getByRole('button',{name:/^Notifications/}).click();
    const inbox=admin.getByRole('region',{name:'Persistent missed-pickup notifications'});const notice=inbox.locator(`[data-notice-id="${report.notification_id}"]`);
    await notice.waitFor();await notice.getByRole('button',{name:'Mark read',exact:true}).click();await notice.getByRole('button',{name:'Mark unread',exact:true}).waitFor();
    await inbox.screenshot({path:path.resolve(__dirname,'../../docs/stage9d-admin.png')});
    const parent=await context.newPage();parent.on('pageerror',e=>errors.push(e.message));const parentQueries=[];
    parent.on('request',r=>{if(r.url().includes('/routing/notifications?'))parentQueries.push(r.url());});
    async function openParent(){await parent.goto('http://127.0.0.1:5173');await parent.getByRole('button',{name:'Parent',exact:true}).click();const dismiss=parent.getByRole('button',{name:'Dismiss notification',exact:true});if(await dismiss.isVisible())await dismiss.click();await parent.getByRole('button',{name:'Open notifications',exact:true}).click();return parent.getByRole('region',{name:'Persistent missed-pickup notifications'});}
    let pinbox=await openParent();assert.equal(parentQueries.length,0,'No parent request without explicit student selection.');
    async function select(id){await pinbox.getByLabel('Notification student ID').fill(id);await pinbox.getByRole('button',{name:'Load selected student notifications',exact:true}).click();}
    await select(report.missed_student_id);let card=pinbox.locator(`[data-notice-id="${report.notification_id}"]`);await card.waitFor();
    await card.getByRole('button',{name:'Mark read',exact:true}).click();await card.getByRole('button',{name:'Mark unread',exact:true}).waitFor();
    // Reconnect/reload requires explicit recipient again and retains stored read state.
    pinbox=await openParent();await select(report.missed_student_id);card=pinbox.locator(`[data-notice-id="${report.notification_id}"]`);
    await card.getByRole('button',{name:'Mark unread',exact:true}).waitFor();
    await pinbox.screenshot({path:path.resolve(__dirname,'../../docs/stage9d-parent.png')});
    for(const id of [report.picked_up_student_id,report.cancelled_student_id,'UNRELATED_EXPLICIT_TEST_ID']){
      await select(id);await pinbox.getByText('No stored missed-pickup events for this recipient.',{exact:true}).waitFor();
      assert.equal(await pinbox.locator('[data-notice-id]').count(),0,'Unrelated recipient must receive no event details.');
    }
    await select(report.missed_student_id);await pinbox.locator(`[data-notice-id="${report.notification_id}"]`).waitFor();
    const pattern='**/api/routing/notifications?**';await parent.route(pattern,r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Stage 9D backend-error fixture'})}));
    await pinbox.getByRole('button',{name:'Refresh in-app events',exact:true}).click();await pinbox.getByText(/Stage 9D backend-error fixture/).waitFor();assert.equal(await pinbox.locator('[data-notice-id]').count(),0);
    await parent.unroute(pattern);await pinbox.getByRole('button',{name:'Refresh in-app events',exact:true}).click();await pinbox.locator(`[data-notice-id="${report.notification_id}"]`).waitFor();
    assert(parentQueries.every(url=>new URL(url).searchParams.get('recipient')==='parent'&&!!new URL(url).searchParams.get('student_id')));
    assert.deepEqual(errors,[]);report.browser={notification_id:report.notification_id,checks:['Admin persisted inbox','explicit Parent recipient required',
      'separate read states','refresh preserves event/read state','picked/cancelled/unrelated selectors receive no event',
      'parent requests always backend-scoped','visible API error without mock fallback'],page_errors:errors};
    fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.browser,null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
