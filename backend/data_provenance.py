"""Fail-closed eligibility for measured datasets; source tags alone are not evidence."""
import math
import re
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from models import (SyntheticTripProvenance, ProvenanceCorrection, VehiclePosition,
                    Vehicle, Trip, RouteVersion)

ARRIVAL_GENERATOR = "backend/tests/test_arrivals.py:ArrivalIntegrationTests"


def register_synthetic_trip(session, trip_id, generator, reason):
    """Internal fixture registration; caller controls its transaction, not a public API."""
    trip = session.get(Trip, trip_id)
    if trip is None or session.get(Vehicle, trip.vehicle_id).input_source != "simulated":
        raise ValueError("Synthetic registration requires an existing simulated vehicle trip.")
    old = session.get(SyntheticTripProvenance, trip_id)
    if old:
        if old.generator != generator or old.reason != reason:
            raise ValueError("Existing immutable fixture registration differs.")
        return
    session.execute(insert(SyntheticTripProvenance).values(trip_id=trip_id, generator=generator,
        reason=reason, registered_at=func.clock_timestamp()).on_conflict_do_nothing(index_elements=["trip_id"]))


def snapshot_sources(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "input_source":
                yield item
            else:
                yield from snapshot_sources(item)
    elif isinstance(value, list):
        for item in value:
            yield from snapshot_sources(item)


def position_exclusion_reason(session, position):
    """Conservative candidate filter, NOT physical-device authentication/quality proof."""
    if position.source != "actual_device":
        return "not_actual_device"
    if session.scalar(select(ProvenanceCorrection.id).where(
            ProvenanceCorrection.entity_table == "vehicle_positions",
            ProvenanceCorrection.entity_key == position.id,
            ProvenanceCorrection.corrected_source == "simulation").limit(1)):
        return "audited_synthetic_position"
    if not position.trip_id:
        return "missing_trip_evidence"
    if session.get(SyntheticTripProvenance, position.trip_id):
        return "registered_synthetic_trip"
    trip = session.get(Trip, position.trip_id)
    vehicle = session.get(Vehicle, position.vehicle_id)
    if not trip or not vehicle or trip.vehicle_id != position.vehicle_id:
        return "invalid_trip_vehicle"
    if vehicle.input_source == "simulated" or re.match(r"^(?:S[4-8]|S9[A-E]|PP1)_", vehicle.id):
        return "synthetic_vehicle_context"
    route = session.get(RouteVersion, trip.route_id)
    sources = list(snapshot_sources(route.input_snapshot)) if route else []
    if not sources or any(source not in ("measured", "live_provider") for source in sources):
        return "synthetic_or_missing_snapshot_provenance"
    if trip.pickup_settings and trip.pickup_settings.get("mode") == "simulation_demo":
        return "simulation_demo_trip"
    return None


def validate_measured_observations(session, observations):
    """Required shared gate before measured-data export OR metric input selection.

    This validates lineage, not segment extraction, consent, device trust or accuracy.
    There is no measured trainer/observation store yet; do not pass this to the
    existing synthetic-only trainer or relabel its targets.
    """
    for observation in observations:
        ids = observation.get("position_ids", [])
        if not isinstance(ids,list) or not 2 <= len(ids) <= 10000 or any(not isinstance(id,str) or not id for id in ids):
            raise ValueError("Observation requires a bounded list of evidence position IDs.")
        if observation.get("data_source") != "measured" or len(set(ids)) < 2:
            raise ValueError("Measured observations require at least two distinct evidence positions.")
        duration = observation.get("duration_s")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Measured duration must be finite and positive.")
        positions = [session.get(VehiclePosition, id) for id in ids]
        for position in positions:
            reason = position_exclusion_reason(session, position) if position else "missing_position"
            if reason:
                raise ValueError(f"Ineligible measured observation: {reason}.")
        if len({(p.trip_id, p.vehicle_id) for p in positions}) != 1:
            raise ValueError("Observation evidence must belong to one vehicle/trip.")
    return observations


def measured_observation_metrics(session, observations, predictions):
    """Lineage gate shared with exports; no model training or target generation."""
    validate_measured_observations(session, observations)
    if not observations or len(observations) != len(predictions):
        raise ValueError("Metrics require matching nonempty measured targets and predictions.")
    if any(isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or p <= 0 for p in predictions):
        raise ValueError("Predictions must be finite and positive.")
    errors=[float(o['duration_s'])-p for o,p in zip(observations,predictions)]
    return {'samples':len(errors),'data_source':'measured',
        'mae_seconds':sum(abs(e) for e in errors)/len(errors),
        'rmse_seconds':math.sqrt(sum(e*e for e in errors)/len(errors))}
