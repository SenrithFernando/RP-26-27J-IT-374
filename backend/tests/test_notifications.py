"""Opt-in persistent missed-event checks using the existing pickup worker fixture server."""
import json
import os
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase,skipUnless
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select,func,insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_engine
from models import Trip,PickupWindow,PickupOutcome,MissedPickupNotification
from notifications import create_missed_event
from pickup_windows import expire_window,outcomes
from pickup_worker import expire_due
import test_pickup_windows as pickup_fixture

@skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS')=='1','Opt in to isolated synthetic notification fixtures.')
class PersistentNotificationTests(TestCase):
    setUpClass=classmethod(pickup_fixture.PickupWindowTests.setUpClass.__func__)
    start_server=classmethod(pickup_fixture.PickupWindowTests.start_server.__func__)
    stop_server=classmethod(pickup_fixture.PickupWindowTests.stop_server.__func__)
    tearDownClass=classmethod(pickup_fixture.PickupWindowTests.tearDownClass.__func__)
    arrive=pickup_fixture.PickupWindowTests.arrive
    windows=pickup_fixture.PickupWindowTests.windows
    def fixture(self,mode='simulation_demo'):
        return pickup_fixture.PickupWindowTests.fixture(self,mode,'per_school',prefix_label='S9D_')
    def test_atomic_expiry_uniqueness_scoping_read_state_and_restart(self):
        trip,route=self.fixture();self.arrive(trip,route)
        window=self.windows(trip)['windows'][0];people=window['outcomes']
        root=f"/trips/{trip['trip_id']}/pickups"
        self.assertEqual(self.client.post(f"{root}/{people[0]['student_id']}/confirm").status_code,200)
        self.assertEqual(self.client.post(f"{root}/{people[1]['student_id']}/cancel",json={'reason':'Synthetic test cancellation'}).status_code,200)
        time.sleep(max(0,(datetime.fromisoformat(window['deadline_at'])-datetime.now(timezone.utc)).total_seconds())+.8)
        with Session(get_engine()) as s:
            notice=s.scalar(select(MissedPickupNotification).where(MissedPickupNotification.trip_id==trip['trip_id']))
            self.assertIsNotNone(notice)
            notice_id=notice.id;created_at=notice.created_at
            self.assertEqual(notice.student_id,people[2]['student_id'])
            self.assertEqual(notice.delivery_status,'in_app_event_created')
            self.assertEqual(notice.position_source,'simulation')
            self.assertIsNotNone(notice.occurred_at.tzinfo);self.assertIsNotNone(notice.created_at.tzinfo)
            # Even a direct duplicate insert is rejected by PostgreSQL uniqueness.
            data={column.name:getattr(notice,column.name) for column in MissedPickupNotification.__table__.columns if column.name not in ('id','order_id')}
            with self.assertRaises(IntegrityError) as duplicate:
                with s.begin_nested():s.execute(insert(MissedPickupNotification).values(id='NOTICE_'+uuid4().hex,**data));s.flush()
            self.assertEqual(duplicate.exception.orig.diag.constraint_name,'one_missed_notification_per_pickup')
        with ThreadPoolExecutor(3) as pool:list(pool.map(lambda _:expire_due(),range(3)))
        with Session(get_engine()) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(MissedPickupNotification).where(MissedPickupNotification.trip_id==trip['trip_id'])),1)
            self.assertEqual(s.get(MissedPickupNotification,notice_id).created_at,created_at)
        def inbox(student=None):
            return self.client.get('/routing/notifications',params={'recipient':'parent','student_id':student} if student else {'recipient':'admin'})
        parent=inbox(people[2]['student_id']).json()
        self.assertEqual([n['id'] for n in parent['notifications']],[notice_id])
        self.assertFalse(parent['notifications'][0]['read'])
        for person in people[:2]:self.assertEqual(inbox(person['student_id']).json()['notifications'],[])
        self.assertEqual(inbox('UNRELATED_EXPLICIT_TEST_ID').json()['notifications'],[])
        self.assertEqual(self.client.get('/routing/notifications',params={'recipient':'parent'}).status_code,422)
        self.assertEqual(self.client.get('/routing/notifications',params={'recipient':'parent','student_id':''}).status_code,422)
        self.assertEqual(self.client.get('/routing/notifications',params={'recipient':'admin','student_id':people[2]['student_id']}).status_code,422)
        self.assertEqual(self.client.get('/routing/notifications',params={'recipient':'admin','limit':201}).status_code,422)
        read_url=f'/routing/notifications/{notice_id}/read'
        self.assertEqual(self.client.patch(read_url,json={'recipient':'parent','student_id':people[0]['student_id'],'read':True}).status_code,404)
        admin=self.client.patch(read_url,json={'recipient':'admin','read':True}).json()
        self.assertTrue(admin['read']);self.assertFalse(inbox(people[2]['student_id']).json()['notifications'][0]['read'])
        marked=self.client.patch(read_url,json={'recipient':'parent','student_id':people[2]['student_id'],'read':True}).json()
        repeated=self.client.patch(read_url,json={'recipient':'parent','student_id':people[2]['student_id'],'read':True}).json()
        self.assertEqual(marked['read_at'],repeated['read_at'])
        self.stop_server();self.start_server()
        refreshed=inbox(people[2]['student_id']).json()['notifications'][0]
        self.assertEqual(refreshed['id'],notice_id);self.assertEqual(refreshed['read_at'],marked['read_at'])
        # Concurrent due processing: three missed students get three events, not duplicates.
        race,rr=self.fixture('production');self.arrive(race,rr);rw=self.windows(race)['windows'][0]
        with Session(get_engine()) as s:
            w=s.get(PickupWindow,rw['window_id']);w.started_at=datetime.now(timezone.utc)-timedelta(seconds=901);w.deadline_at=w.started_at+timedelta(seconds=900);s.commit()
        with ThreadPoolExecutor(3) as pool:list(pool.map(lambda _:expire_due(),range(3)))
        with Session(get_engine()) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(MissedPickupNotification).where(MissedPickupNotification.trip_id==race['trip_id'])),3)
            self.assertEqual(s.scalar(select(func.count(func.distinct(MissedPickupNotification.student_id))).where(MissedPickupNotification.trip_id==race['trip_id'])),3)
        # Failure to insert event must roll back the MISSED transition in the same transaction.
        atomic,ar=self.fixture('production');self.arrive(atomic,ar);aw=self.windows(atomic)['windows'][0]
        with Session(get_engine()) as s:
            s.scalar(select(Trip).where(Trip.id==atomic['trip_id']).with_for_update())
            w=s.scalar(select(PickupWindow).where(PickupWindow.id==aw['window_id']).with_for_update())
            w.started_at=datetime.now(timezone.utc)-timedelta(seconds=901);w.deadline_at=w.started_at+timedelta(seconds=900)
            rows=outcomes(s,w)
            with patch('notifications.create_missed_event',side_effect=RuntimeError('Synthetic transactional failure')):
                with self.assertRaises(RuntimeError):expire_window(s,w,rows,datetime.now(timezone.utc),'expiry_test')
            s.rollback()
        with Session(get_engine()) as s:
            self.assertEqual(s.get(PickupWindow,aw['window_id']).state,'WAITING')
            self.assertTrue(all(row.state=='WAITING' for row in s.scalars(select(PickupOutcome).where(PickupOutcome.trip_id==atomic['trip_id']))))
            self.assertEqual(s.scalar(select(func.count()).select_from(MissedPickupNotification).where(MissedPickupNotification.trip_id==atomic['trip_id'])),0)
        self.assertEqual(self.client.post(f"/trips/{atomic['trip_id']}/cancel",json={'reason':'Synthetic atomicity test complete'}).status_code,200)
        report={'trip_id':trip['trip_id'],'vehicle_id':trip['vehicle_id'],'notification_id':notice_id,
            'missed_student_id':people[2]['student_id'],'picked_up_student_id':people[0]['student_id'],'cancelled_student_id':people[1]['student_id'],
            'events_for_mixed_window':1,'events_for_three_missed_students':3,'delivery_status':'in_app_event_created',
            'checks':['real worker expiry event','one event after repeated/concurrent processing','PostgreSQL unique constraint enforced',
                'admin and student-scoped parent inbox','unrelated/picked/cancelled students receive no missed alert','mismatched parent read rejected',
                'independent admin/parent read state','read state and event survive backend restart','MISSED/event transaction rollback together'],
            'data_source':'isolated synthetic S9D fixtures; no SMS/push delivery or real authentication'}
        output=Path('../docs/stage9d_verification.json')
        if output.exists():
            previous=json.loads(output.read_text(encoding='utf-8'))
            if previous.get('browser'):report['browser']=previous['browser']
        output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
