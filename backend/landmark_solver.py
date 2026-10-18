"""Opt-in grouped-school policy. All costs fetched once, never in callbacks."""
from time import perf_counter
from collections import Counter
from ortools.constraint_solver import pywrapcp,routing_enums_pb2
from route_solver import Event,failure
from travel_time import Coordinate,validate_costs,InvalidTravelCosts


def solve_landmark(vehicle,students,schools,settings,provider):
    am=settings.direction=='morning'
    if settings.departure_seconds<(21600 if am else 48600):return failure('invalid_input',['Departure must be at/after 06:00 AM or 13:30 PM respectively.'])
    if not students:return failure('empty',['No confirmed eligible participants for this direction.'])
    if vehicle.capacity<=0 or len(students)>vehicle.capacity:return failure('infeasible',['All participants are onboard before any delivery; assigned roster exceeds usable capacity.'])
    if any(s.vehicle_id!=vehicle.id or s.school_id not in schools for s in students):return failure('invalid_input',['Invalid fixed assignment.'])
    if not vehicle.start.valid() or not vehicle.end.valid() or any(not s.home.valid() for s in students) or any(not s.location.valid() for s in schools.values()):return failure('invalid_input',['Unconfirmed or missing landmark/depot/school coordinates; review pins. No coordinates were invented.'])
    school_list=sorted(schools.values(),key=lambda s:s.id)
    if len(school_list)!=2:return failure('invalid_input',['This isolated policy requires both mapped schools.'])
    groups={s.id:[p.id for p in students if p.school_id==s.id] for s in school_list}
    events=[];members={}
    def add(event,ids):
        members[len(events)]=ids;events.append(event);return len(events)-1
    if am:
        add(Event('depot:start',vehicle.id+':start','Depot departure','start',vehicle.start),[])
    else:
        b=school_list[1]
        add(Event(b.id+':boarding',b.id,b.name,'pickup',b.location,school_id=b.id,demand=len(groups[b.id]),service_seconds=900,earliest_seconds=48600),groups[b.id])
    homes=[];school_nodes=[]
    for p in students:
        homes.append(add(Event(p.id+':'+('pickup' if am else 'delivery'),p.home_id,p.name,'pickup' if am else 'delivery',p.home,p.id,p.school_id,1 if am else -1,120),[p.id]))
    for s in school_list:
        if not am and s is school_list[1]:school_nodes.append(0);continue
        school_nodes.append(add(Event(s.id+':group',s.id,s.name,'delivery' if am else 'pickup',s.location,school_id=s.id,demand=-len(groups[s.id]) if am else len(groups[s.id]),service_seconds=600 if am else 900,earliest_seconds=0 if am else 48600,latest_seconds=26100 if am else 86400),groups[s.id]))
    # AM has a true zero-cost virtual sink, omitted from the returned stops.
    real_count=len(events);end=real_count if am else add(Event('depot:end',vehicle.id+':end','Depot return','end',vehicle.end),[])
    n=real_count+1 if am else len(events)
    try:
        costs=provider.precompute([Coordinate(e.location.latitude,e.location.longitude,e.location_id) for e in events],settings.direction,settings.departure_seconds)
        validate_costs(costs,len(events))
        if costs.metadata.get('has_unavailable_pairs'):raise InvalidTravelCosts('Some directed pairs unavailable.')
    except InvalidTravelCosts as error:return failure('unavailable',[str(error)])
    def duration(a,b):return 0 if am and b==end else costs.duration_seconds[a][b]
    manager=pywrapcp.RoutingIndexManager(n,1,[0],[end]);routing=pywrapcp.RoutingModel(manager)
    def transit(i,j):
        a,b=manager.IndexToNode(i),manager.IndexToNode(j)
        return events[a].service_seconds+duration(a,b)
    cb=routing.RegisterTransitCallback(transit);routing.SetArcCostEvaluatorOfAllVehicles(cb)
    horizon=min(172800,settings.departure_seconds+settings.max_route_seconds)
    routing.AddDimension(cb,settings.max_route_seconds,horizon,False,'Time');time=routing.GetDimensionOrDie('Time')
    time.CumulVar(routing.Start(0)).SetValue(settings.departure_seconds)
    for node,e in enumerate(events):
        if node in (0,end):continue
        lo=max(settings.departure_seconds,e.earliest_seconds);hi=min(horizon,e.latest_seconds)
        if lo>hi:return failure('infeasible',['Hard school arrival/release bounds cannot be met.'])
        time.CumulVar(manager.NodeToIndex(node)).SetRange(lo,hi)
        if am and node in school_nodes:time.SetCumulVarSoftUpperBound(manager.NodeToIndex(node),25500,100)
    demand=routing.RegisterUnaryTransitCallback(lambda i:events[manager.IndexToNode(i)].demand)
    routing.AddDimensionWithVehicleCapacity(demand,0,[vehicle.capacity],True,'Load')
    routing.GetDimensionOrDie('Load').CumulVar(routing.End(0)).SetValue(0)
    routing.AddConstantDimension(1,n+1,True,'Order');order=routing.GetDimensionOrDie('Order');solver=routing.solver()
    for h in homes:
        for s in school_nodes:
            a,b=(h,s) if am else (s,h)
            solver.Add(order.CumulVar(manager.NodeToIndex(a))+1<=order.CumulVar(manager.NodeToIndex(b)))
    for i in range(routing.Size()):routing.AddVariableMinimizedByFinalizer(time.CumulVar(i))
    routing.AddVariableMinimizedByFinalizer(time.CumulVar(routing.End(0)))
    params=pywrapcp.DefaultRoutingSearchParameters();params.first_solution_strategy=routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic=routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH;params.time_limit.seconds=settings.solver_time_limit_seconds
    began=perf_counter();solution=routing.SolveWithParameters(params);runtime=round(perf_counter()-began,6)
    if solution is None:return failure('no_solution_found',['No feasible grouped route within hard bounds and bounded search.'],costs.metadata,runtime)
    stops=[];index=routing.Start(0);load=0;previous=None;leave=settings.departure_seconds
    while True:
        node=manager.IndexToNode(index)
        if am and node==end:break
        e=events[node];drive=0 if previous is None else duration(previous,node);dist=0 if previous is None else costs.distance_metres[previous][node]
        arrival=leave+drive;eta=solution.Value(time.CumulVar(index));before=load;load+=e.demand
        source={'source':'start','fallback_reason':None} if previous is None else costs.leg_sources[previous][node] if costs.leg_sources else {'source':costs.metadata['duration_source']}
        stops.append(dict(sequence=len(stops)+1,event_id=e.id,location_id=e.location_id,name=e.name,action=e.action,student_id=e.student_id,student_ids=members[node],student_names={p.id:p.name for p in students if p.id in members[node]},school_id=e.school_id,latitude=e.location.latitude,longitude=e.location.longitude,address=e.location.address,input_source=e.location.input_source,location_method=e.location.location_method,arrival_seconds=arrival,eta_seconds=eta,departure_seconds=eta+e.service_seconds,driving_seconds_from_previous=drive,distance_metres_from_previous=dist,service_seconds=e.service_seconds,waiting_seconds=eta-arrival,load_before=before,load_after=load,travel_source=source,grouped=e.student_id is None and e.action in ('pickup','delivery')))
        leave=eta+e.service_seconds;previous=node
        if routing.IsEnd(index):break
        index=solution.Value(routing.NextVar(index))
    result=dict(feasibility_status='feasible',errors=[],stops=stops,solver_runtime_seconds=runtime,solver_status='feasible_bounded_search',provider_source=dict(costs.metadata),optimality='Feasible heuristic; no proven global optimum.',total_duration_seconds=leave-settings.departure_seconds,
        preferred_buffer_met=all(s['eta_seconds']<=25500 for s in stops if s['grouped']) if am else None,
        warnings=['Preferred 07:05 arrival buffer not met at every school; hard 07:15 remains enforced.'] if am and any(s['eta_seconds']>25500 for s in stops if s['grouped']) else [],end_policy='last_school_no_depot_return' if am else 'SCH_B_then_SCH_A_then_homes_then_depot')
    for total,field in [('driving_seconds','driving_seconds_from_previous'),('distance_metres','distance_metres_from_previous'),('service_seconds','service_seconds'),('waiting_seconds','waiting_seconds')]:result[total]=sum(s[field] for s in stops)
    counts=Counter(s['travel_source']['source'] for s in stops if s['travel_source']['source'] not in ('start','geographic_zero'))
    result['provider_source'].update(duration_source=next(iter(counts)) if len(counts)==1 else 'mixed' if counts else 'geographic_zero',route_source_counts=dict(counts),route_fallback_reasons=sorted({s['travel_source']['fallback_reason'] for s in stops if s['travel_source'].get('fallback_reason')}))
    validate_landmark(result,vehicle,students,schools,settings)
    return result


def validate_landmark(result,vehicle,students,schools,settings):
    stops=result['stops'];am=settings.direction=='morning';roster={p.id:p for p in students}
    pickups={};deliveries={};load=0;school_ids=[]
    for i,s in enumerate(stops):
        assert s['load_before']==load and s['waiting_seconds']>=0
        if i:assert s['arrival_seconds']==stops[i-1]['departure_seconds']+s['driving_seconds_from_previous']
        if s['grouped']:
            school_ids.append(s['school_id']);assert set(s['student_ids'])=={p.id for p in students if p.school_id==s['school_id']}
            loc=schools[s['school_id']].location
            assert (s['latitude'],s['longitude'])==(loc.latitude,loc.longitude)
            assert s['service_seconds']==(600 if am else 900)
            assert (s['eta_seconds']<=26100 and s['departure_seconds']<27000) if am else s['eta_seconds']>=48600
        elif s['action'] in ('pickup','delivery'):
            p=roster[s['student_id']];assert s['school_id']==p.school_id and s['service_seconds']==120
            assert (s['latitude'],s['longitude'])==(p.home.latitude,p.home.longitude)
        for sid in s['student_ids']:
            if s['action']=='pickup':assert sid not in pickups;pickups[sid]=i;load+=1
            elif s['action']=='delivery':assert sid in pickups and pickups[sid]<i and sid not in deliveries;deliveries[sid]=i;load-=1
        assert 0<=load<=vehicle.capacity and s['load_after']==load
    assert set(pickups)==set(deliveries)==set(roster) and load==0 and set(school_ids)==set(schools) and len(school_ids)==2
    assert max(pickups.values())<min(deliveries.values())
    if am:assert stops[0]['action']=='start' and stops[-1]['grouped'] and stops[-1]['action']=='delivery'
    else:assert stops[0]['school_id']==sorted(schools)[1] and stops[0]['action']=='pickup' and stops[-1]['action']=='end'
    assert result['total_duration_seconds']==sum(result[k] for k in ['driving_seconds','service_seconds','waiting_seconds'])
