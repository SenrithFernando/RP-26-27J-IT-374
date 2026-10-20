"""No database writes: navigation confirmation uses only saved snapshot coordinates."""
from types import SimpleNamespace as Row
from unittest import TestCase
from route_service import saved_stop_location_confirmed

class SavedNavigationTests(TestCase):
 def test_school_home_and_depot_confirmation_from_fixed_snapshot(self):
  loc={'latitude':6.9,'longitude':79.9,'confirmed':True}
  version=Row(input_snapshot={'vehicle':{'id':'V','start':dict(loc),'end':dict(loc)},
    'schools':{'S':{'location':dict(loc)}},'students':[{'home_id':'H','home':dict(loc)}]})
  for key in ('S','H','V:start','V:end'):
   with self.subTest(key=key):self.assertTrue(saved_stop_location_confirmed(version,Row(location_id=key,latitude=6.9,longitude=79.9)))
  self.assertFalse(saved_stop_location_confirmed(version,Row(location_id='S',latitude=6.91,longitude=79.9)))
  version.input_snapshot['schools']['S']['location']['confirmed']=False
  self.assertFalse(saved_stop_location_confirmed(version,Row(location_id='S',latitude=6.9,longitude=79.9)))
 def test_legacy_missing_confirmation_fails_closed(self):
  self.assertFalse(saved_stop_location_confirmed(Row(input_snapshot={}),Row(location_id='S',latitude=6.9,longitude=79.9)))
