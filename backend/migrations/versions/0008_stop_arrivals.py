"""Current stop selection and durable GPS proximity arrivals."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision="0008_stop_arrivals"
down_revision="0007_vehicle_positions"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("trips",sa.Column("current_stop_sequence",sa.Integer()))
    op.add_column("trips",sa.Column("current_stop_selected_at",sa.DateTime(timezone=True)))
    op.add_column("trips",sa.Column("arrival_settings",JSONB()))
    # Existing active trips start monitoring now, never retroactively process old positions.
    op.execute("UPDATE trips SET current_stop_sequence=(SELECT min(sequence) FROM route_stops WHERE route_id=trips.route_id AND action <> 'start'), current_stop_selected_at=now() WHERE state='ACTIVE'")
    op.create_table("trip_stop_arrivals",
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),primary_key=True),
        sa.Column("stop_sequence",sa.Integer(),primary_key=True),
        sa.Column("route_id",sa.String(64),sa.ForeignKey("route_versions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("candidate_started_at",sa.DateTime(timezone=True)),
        sa.Column("last_recorded_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("observation_count",sa.Integer(),nullable=False),
        sa.Column("distance_metres",sa.Float(),nullable=False),
        sa.Column("source",sa.String(24),nullable=False),
        sa.Column("event_id",sa.String(64),unique=True),
        sa.Column("arrived_at",sa.DateTime(timezone=True)),
        sa.Column("confirming_position_id",sa.String(64),sa.ForeignKey("vehicle_positions.id",ondelete="RESTRICT")),
        sa.CheckConstraint("observation_count >= 0",name="arrival_observations"),
        sa.CheckConstraint("(arrived_at IS NULL AND event_id IS NULL AND confirming_position_id IS NULL) OR (arrived_at IS NOT NULL AND event_id IS NOT NULL AND confirming_position_id IS NOT NULL)",name="arrival_event_complete"))


def downgrade():
    raise RuntimeError("Archive arrival evidence before explicitly removing this migration.")
