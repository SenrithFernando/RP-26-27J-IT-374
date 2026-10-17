"""Reprice alternative stop orders using the exact frozen solver matrix."""
def compare_alternatives(result, events, costs, settings, vehicle, students, schools, reference_stops, audit):
    by_id = {event.id: i for i,event in enumerate(events)}
    expected = set(by_id)
    prior_ids = [s['event_id'] for s in reference_stops] if reference_stops else []
    if len(prior_ids) == len(events) and set(prior_ids) == expected and prior_ids[0] == events[0].id and prior_ids[-1] == events[1].id:
        order = [by_id[id] for id in prior_ids]; label = 'Previous stop order repriced under this snapshot'
    else:
        order = [0, *range(2,len(events)), 1]; label = 'Registered student order (pickup then delivery) under this snapshot'
    stops, load, previous, clock = [], 0, None, settings.departure_seconds
    violations = []
    for node in order:
        event = events[node]
        driving = 0 if previous is None else costs.duration_seconds[previous][node]
        distance = 0 if previous is None else costs.distance_metres[previous][node]
        arrival = clock + driving
        eta = max(arrival, event.earliest_seconds) if node not in (0,1) else arrival
        if eta > event.latest_seconds or eta > settings.departure_seconds + settings.max_route_seconds:
            violations.append(f'{event.id} exceeds its current time window/horizon.')
        before = load; load += event.demand
        stops.append({'sequence': len(stops)+1, 'event_id': event.id, 'action': event.action,
            'student_id': event.student_id, 'school_id': event.school_id, 'location_id': event.location_id,
            'latitude': event.location.latitude, 'longitude': event.location.longitude, 'load_before': before, 'load_after': load,
            'arrival_seconds': arrival, 'eta_seconds': eta, 'departure_seconds': eta+event.service_seconds,
            'waiting_seconds': eta-arrival, 'service_seconds': event.service_seconds,
            'driving_seconds_from_previous': driving, 'distance_metres_from_previous': distance})
        clock = eta+event.service_seconds; previous = node
    metrics = {'distance_metres': sum(s['distance_metres_from_previous'] for s in stops),
        'driving_seconds': sum(s['driving_seconds_from_previous'] for s in stops),
        'service_seconds': sum(s['service_seconds'] for s in stops), 'waiting_seconds': sum(s['waiting_seconds'] for s in stops),
        'total_duration_seconds': clock-settings.departure_seconds}
    candidate = {**metrics, 'stops': stops}
    if not violations:
        try: audit(candidate, vehicle, students, schools, settings)
        except RuntimeError as error: violations.append(str(error))
    fields = list(metrics)
    return {'matrix_snapshot_id': costs.metadata.get('matrix_snapshot_id'), 'traffic_scenario': costs.metadata.get('traffic_scenario', 'normal'),
        'same_matrix': True, 'reference_label': label, 'reference_feasibility_status': 'infeasible' if violations else 'feasible',
        'reference_errors': violations, 'reference': None if violations else metrics,
        'selected': {field: result[field] for field in fields},
        'reference_minus_selected': {field: None if violations else metrics[field]-result[field] for field in fields},
        'sequence_changed': [s['event_id'] for s in stops] != [s['event_id'] for s in result['stops']],
        'note': 'Both stop orders use identical departure-time matrix values, scenario and current service/window constraints. No old normal-traffic costs are used; zero or negative differences are valid.'}
