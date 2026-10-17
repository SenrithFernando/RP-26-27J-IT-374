"""Synthetic GPS cannot silently become measured export/metric input."""
from pathlib import Path
from datetime import datetime, timezone
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as Row
from unittest import TestCase
from unittest.mock import Mock
from models import (VehiclePosition,Vehicle,Trip,RouteVersion,SyntheticTripProvenance)
from data_provenance import (position_exclusion_reason,validate_measured_observations,
    measured_observation_metrics)
from export_measured_observations import export_observations
from correct_fixture_provenance import correct_field, verify_fixture


def context(source='actual_device',fixture=False,vehicle_source='measured',snapshot_source='measured'):
    positions={id:Row(id=id,source=source,trip_id='T',vehicle_id='REAL_V') for id in ['P1','P2']}
    registry=Row(trip_id='T') if fixture else None
    def get(model,key):
        if model is VehiclePosition:return positions.get(key)
        if model is SyntheticTripProvenance:return registry
        if model is Vehicle:return Row(id='REAL_V',input_source=vehicle_source)
        if model is Trip:return Row(vehicle_id='REAL_V',route_id='R',pickup_settings={'mode':'production'})
        if model is RouteVersion:return Row(input_snapshot={'vehicle':{'start':{'input_source':snapshot_source}}})
    session=Mock();session.get.side_effect=get;session.scalar.return_value=None
    return session,positions


class MeasuredLineageTests(TestCase):
    observation={'data_source':'measured','duration_s':100,'position_ids':['P1','P2']}

    def test_spoofed_actual_device_fixture_rejected_by_export_and_metrics(self):
        session,positions=context(fixture=True)
        self.assertEqual(position_exclusion_reason(session,positions['P1']),'registered_synthetic_trip')
        with TemporaryDirectory() as directory:
            output=Path(directory)/'measured.json';output.write_text('preserve existing export',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'registered_synthetic_trip'):
                export_observations(session,[self.observation],output)
            self.assertEqual(output.read_text(encoding='utf-8'),'preserve existing export')
        with self.assertRaisesRegex(ValueError,'registered_synthetic_trip'):
            measured_observation_metrics(session,[self.observation],[90])

    def test_relabelled_simulation_and_legacy_unregistered_fixtures_are_excluded(self):
        for values,reason in [({'source':'simulation'},'not_actual_device'),
            ({'vehicle_source':'simulated'},'synthetic_vehicle_context'),
            ({'snapshot_source':'simulated'},'synthetic_or_missing_snapshot_provenance')]:
            session,_=context(**values)
            with self.assertRaisesRegex(ValueError,reason):validate_measured_observations(session,[self.observation])
        session,_=context();session.scalar.return_value='PROV_EXISTING'
        with self.assertRaisesRegex(ValueError,'audited_synthetic_position'):
            validate_measured_observations(session,[self.observation])

    def test_no_blanket_rejection_of_nonfixture_declared_device_evidence(self):
        session,positions=context()
        self.assertIsNone(position_exclusion_reason(session,positions['P1']))
        self.assertEqual(measured_observation_metrics(session,[self.observation],[90])['mae_seconds'],10)
        with TemporaryDirectory() as directory:
            output=Path(directory)/'measured.json'
            self.assertEqual(export_observations(session,[self.observation],output),1)
            original=output.read_text(encoding='utf-8')
            self.assertEqual(json.loads(original),[self.observation])
            # A valid first row cannot cause a partial export before a bad row fails.
            with self.assertRaises(ValueError):
                export_observations(session,[self.observation,{**self.observation,'data_source':'synthetic'}],output)
            self.assertEqual(output.read_text(encoding='utf-8'),original)

    def test_correction_is_idempotent_and_unknown_identity_fails_closed(self):
        session=Mock();session.scalar.return_value=datetime.now(timezone.utc)
        row=Row(source='actual_device');changes=[]
        for _ in range(2):correct_field(session,row,'vehicle_positions','P','source',{'actual_device':'simulation'},changes)
        self.assertEqual(len(changes),1);session.add.assert_called_once()
        audit=session.add.call_args.args[0]
        self.assertEqual((audit.previous_source,audit.corrected_source),('actual_device','simulation'))
        session.get.return_value=None
        with self.assertRaises(ValueError):verify_fixture(session,'unreviewed','V','T')
