"""Bounded minute-grid search. Never assumes FIFO/monotonic travel estimates."""
from dataclasses import replace
from datetime import datetime, timezone
from time import monotonic
from landmark_solver import solve_landmark
from route_solver import failure
from traffic_provider import SNAPSHOT_LIMITATION

EARLIEST=21600
PREFERRED=25500
HARD=26100
RESOLUTION=60
MAX_SECONDS=30


class BudgetExceeded(Exception):pass


class CandidateMatrices:
    """One precomputation per departure; preferred/hard passes share the same costs."""
    def __init__(self,provider,budget,deadline):
        self.provider,self.budget,self.deadline=provider,budget,deadline
        self.cache={}
    def precompute(self,coordinates,direction,departure):
        if monotonic()>=self.deadline:raise BudgetExceeded()
        if departure not in self.cache:
            if len(self.cache)>=self.budget:raise BudgetExceeded()
            self.cache[departure]=self.provider.precompute(coordinates,direction,departure)
        return self.cache[departure]


def recommend(vehicle,students,schools,settings,provider,*,live_budget=0,google=False):
    began=monotonic();matrices=CandidateMatrices(provider,live_budget if google else 76,began+MAX_SECONDS)
    http_requests=0
    if google:
        from traffic_google import ProviderFailure
        transport=provider.live.transport
        def bounded_transport(*args):
            nonlocal http_requests
            if http_requests>=live_budget or monotonic()>=matrices.deadline:
                raise ProviderFailure('recommendation_budget','Explicit departure recommendation HTTP budget exhausted; live estimate unavailable.')
            http_requests+=1
            bounded_args=(*args[:-1],min(args[-1],max(.01,matrices.deadline-monotonic())))
            return transport(*bounded_args)
        provider.live.transport=bounded_transport
    attempts=0;solver_seconds=0;last=None;selected=None;preferred_complete=False;status='search_incomplete'
    try:
        # Descending exhaustive grid, not binary search: ML/live costs need not be monotonic.
        for preferred,upper in [(True,PREFERRED),(False,HARD)]:
            for departure in range(upper,EARLIEST-1,-RESOLUTION):
                if monotonic()>=matrices.deadline:raise BudgetExceeded()
                attempts+=1
                last=solve_landmark(vehicle,students,schools,replace(settings,departure_seconds=departure),matrices,
                    preferred_required=preferred,feasibility_only=True)
                solver_seconds+=last.get('solver_runtime_seconds') or 0
                if last['feasibility_status']=='feasible':
                    selected=departure;status='preferred_feasible' if preferred else 'reduced_buffer';break
                if last['feasibility_status'] in ('invalid_input','empty','unavailable','infeasible'):
                    # Capacity/coordinates/empty roster are departure independent. Time-bound
                    # infeasibility is not, and must continue toward earlier departures.
                    if last['feasibility_status']!='infeasible' or any('capacity' in e for e in last['errors']):
                        status='inputs_unavailable';break
            else:
                if preferred:preferred_complete=True;continue
                status='no_feasible_departure_found';break
            break
    except BudgetExceeded:
        status='search_incomplete'
    result=last if selected is not None else failure('no_solution_found' if status=='no_feasible_departure_found' else 'unavailable',[
        'No feasible departure found at/after 06:00 on the one-minute grid within bounded solver searches; infeasibility is not proven.'
        if status=='no_feasible_departure_found' else 'Departure search incomplete or inputs unavailable; no recommendation. Review inputs or the explicit request/time budget.',*(last.get('errors',[]) if last else [])])
    result['departure_recommendation']={
        'mode':'recommend','status':status,'recommended_departure_seconds':selected,
        'preferred_feasible':True if status=='preferred_feasible' else False if preferred_complete else None,
        'hard_feasible':True if selected is not None else None,
        'resolution_seconds':RESOLUTION,'earliest_departure_seconds':EARLIEST,
        'preferred_arrival_seconds':PREFERRED,'hard_arrival_seconds':HARD,
        'matrix_evaluations':len(matrices.cache),'matrix_budget':matrices.budget,
        'live_http_requests':http_requests,'live_http_request_budget':live_budget if google else 0,
        'solver_attempts':attempts,'solver_attempt_budget':142,'wall_time_budget_seconds':MAX_SECONDS,
        'search_runtime_seconds':round(monotonic()-began,6),
        'estimate_timestamp':datetime.now(timezone.utc).isoformat(),
        'assumptions':[SNAPSHOT_LIMITATION,'Latest feasible departure found on a one-minute grid; bounded heuristic feasibility searches, no global proof.',
            'Both schools constrained independently; 120 s per home pickup and 600 s per school; no second safety-buffer subtraction.',
            'All pickups precede grouped deliveries; morning ends at last school without depot return.',
            'Google budget caps actual HTTP requests and candidate matrix invocations; cache hits do not consume HTTP budget; no geometry requests.'],
    }
    result['solver_runtime_seconds']=round(solver_seconds,6)
    return result,selected


def override_evidence(result,departure):
    feasible=result['feasibility_status']=='feasible'
    return {'mode':'override','status':'preferred_feasible' if feasible and result.get('preferred_buffer_met') else 'reduced_buffer' if feasible else 'override_not_feasible',
        'recommended_departure_seconds':None,'override_departure_seconds':departure,
        'preferred_feasible':result.get('preferred_buffer_met') if feasible else None,'hard_feasible':feasible,
        'estimate_timestamp':datetime.now(timezone.utc).isoformat(),
        'assumptions':[SNAPSHOT_LIMITATION,'Administrator override re-solved against every school and service constraint; no deadline relaxation.']}
