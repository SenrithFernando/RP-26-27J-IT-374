"""Controlled synthetic costs only; no provider network or database writes."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from test_dual_route_solver import fixture
from travel_time import TravelCosts
from routing_domain import GenerationSettings
from departure_recommendation import recommend,override_evidence
from landmark_solver import solve_landmark
from route_schemas import GenerateRouteRequest
from pydantic import ValidationError

class Costs:
 def __init__(self,edge=0,time_effect=False):self.edge=edge;self.time_effect=time_effect;self.calls=[]
 def precompute(self,points,direction,departure):
  self.calls.append(departure);n=len(points)
  cost=self.edge+(60 if self.time_effect and departure>=24000 else 0)
  return TravelCosts([[0 if i==j else cost for j in range(n)] for i in range(n)],[[0]*n for _ in range(n)],{'duration_source':'simulation','provider':'controlled_synthetic_test','distance_source':'synthetic','distance_is_approximate':True})

class DepartureTests(unittest.TestCase):
 def setUp(self):
  self.v,self.people,self.schools=fixture();self.v=replace(self.v,capacity=20);self.settings=GenerationSettings('morning',21600,solver_time_limit_seconds=1)
 def search(self,p):return recommend(self.v,self.people,self.schools,self.settings,p)
 def test_both_school_service_and_latest_minute(self):
  r,d=self.search(Costs());self.assertEqual(d,24420)
  self.assertEqual(r['departure_recommendation']['status'],'preferred_feasible')
  groups=[s for s in r['stops'] if s['grouped']]
  self.assertEqual(len(groups),2);self.assertEqual(groups[-1]['eta_seconds'],25500)
  self.assertEqual(groups[0]['departure_seconds'],groups[-1]['eta_seconds'])
  self.assertEqual(r['service_seconds'],1680);self.assertEqual(r['total_duration_seconds'],1680)
  later=solve_landmark(self.v,self.people,self.schools,replace(self.settings,departure_seconds=d+60),Costs(),preferred_required=True,feasibility_only=True)
  self.assertNotEqual(later['feasibility_status'],'feasible')
 def test_each_school_constrains_not_only_named_final_school(self):
  # Swap names/IDs/assignments: whichever school is first still consumes 600 s
  # before the other school; both have independent hard preferred constraints.
  for reverse in (False,True):
   schools=dict(reversed(list(self.schools.items()))) if reverse else self.schools
   r,d=recommend(self.v,self.people,schools,self.settings,Costs(60))
   self.assertEqual(d,24060)
   self.assertTrue(all(s['eta_seconds']<=25500 for s in r['stops'] if s['grouped']))
 def test_reduced_buffer_distinct_from_no_departure(self):
  r,d=self.search(Costs(500));self.assertEqual(d,22020)
  self.assertEqual(r['departure_recommendation']['status'],'reduced_buffer')
  self.assertFalse(r['departure_recommendation']['preferred_feasible'])
  self.assertTrue(all(s['eta_seconds']<=26100 and s['departure_seconds']<27000 for s in r['stops'] if s['grouped']))
  r,d=self.search(Costs(700));self.assertIsNone(d)
  self.assertEqual(r['departure_recommendation']['status'],'no_feasible_departure_found')
 def test_candidate_time_costs_nonmonotonic_no_binary_assumption(self):
  p=Costs(time_effect=True);r,d=self.search(p)
  self.assertEqual(d,24060);self.assertEqual(len(p.calls),len(set(p.calls)))
  self.assertTrue(all(x>=21600 for x in p.calls))
 def test_override_revalidated(self):
  for departure,feasible in [(21599,False),(24420,True),(26000,False)]:
   r=solve_landmark(self.v,self.people,self.schools,replace(self.settings,departure_seconds=departure),Costs(),feasibility_only=True)
   self.assertEqual(override_evidence(r,departure)['hard_feasible'],feasible)
 def test_exact_earliest_departure_and_terminal_service_no_return(self):
  # Four pickups + two school visits: six driven arcs before the virtual sink.
  # At 570 s/arc, arrival at the final school is exactly the hard 07:15
  # boundary when departing 06:00. Its 600 s service is still included.
  r,d=self.search(Costs(570))
  self.assertEqual(d,21600)
  self.assertEqual(r['departure_recommendation']['status'],'reduced_buffer')
  self.assertEqual(r['stops'][-1]['eta_seconds'],26100)
  self.assertEqual(r['stops'][-1]['departure_seconds'],26700)
  self.assertEqual(r['driving_seconds'],3420)
  self.assertEqual(r['service_seconds'],1680)
  self.assertEqual(r['waiting_seconds'],0)
  self.assertEqual(r['total_duration_seconds'],5100)
  self.assertEqual(r['end_policy'],'last_school_no_depot_return')
  self.assertEqual(len([s for s in r['stops'] if s['grouped']]),2)
  self.assertEqual(r['stops'][-1]['action'],'delivery')
  r,d=self.search(Costs(571))
  self.assertIsNone(d)
  self.assertEqual(r['departure_recommendation']['status'],'no_feasible_departure_found')
 def test_budget_exhaustion_and_invalid_google_optin(self):
  from types import SimpleNamespace
  p=Costs();p.live=SimpleNamespace(transport=lambda *a:None)
  r,d=recommend(self.v,self.people,self.schools,self.settings,p,google=True,live_budget=1)
  self.assertIsNone(d);self.assertEqual(r['departure_recommendation']['status'],'search_incomplete')
  self.assertEqual(len(p.calls),1)
  with self.assertRaises(ValidationError):GenerateRouteRequest(vehicle_id='x',direction='morning',departure_seconds=21600,departure_mode='recommend',provider='google')
 def test_unavailable_does_not_fabricate_recommendation(self):
  v=replace(self.v,start=replace(self.v.start,confirmed=False))
  r,d=recommend(v,self.people,self.schools,self.settings,Costs())
  self.assertIsNone(d);self.assertEqual(r['departure_recommendation']['status'],'inputs_unavailable')
 def test_google_http_budget_is_transport_wide_no_paid_calls(self):
  from traffic_google import GoogleRoutesAdapter,BoundedCache
  from traffic_provider import TrafficSnapshotProvider
  calls=[]
  def fake_transport(method,body,fields,key,timeout):
   calls.append(method)
   return [dict(originIndex=i,destinationIndex=j,condition='ROUTE_EXISTS',distanceMeters=1,duration='1s') for i in range(len(body['origins'])) for j in range(len(body['destinations']))]
  live=GoogleRoutesAdapter({'key':'synthetic-test-only','map_key':'','timeout':1,'budget':2},transport=fake_transport,store=BoundedCache(ttl=0))
  request=GenerateRouteRequest(vehicle_id=self.v.id,direction='morning',service_date='2099-10-19',departure_seconds=21600,provider='google',fallback_policy='none')
  provider=TrafficSnapshotProvider(request,live=live)
  r,d=recommend(self.v,self.people,self.schools,self.settings,provider,google=True,live_budget=1)
  self.assertEqual(len(calls),1);self.assertIsNone(d)
  self.assertEqual(r['departure_recommendation']['live_http_requests'],1)

if __name__=='__main__':unittest.main()
