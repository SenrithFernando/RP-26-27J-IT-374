"""Persistent pickup visits, per-student outcomes, transition audit."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision="0009_pickup_windows"
down_revision="0008_stop_arrivals"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("trips",sa.Column("pickup_settings",JSONB()))
    op.create_table("pickup_windows",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("route_id",sa.String(64),sa.ForeignKey("route_versions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("scope_key",sa.String(200),nullable=False),sa.Column("scope",sa.String(16),nullable=False),
        sa.Column("school_id",sa.String(64)),sa.Column("state",sa.String(16),nullable=False),
        sa.Column("mode",sa.String(24),nullable=False),sa.Column("duration_seconds",sa.Integer(),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("deadline_at",sa.DateTime(timezone=True)),
        sa.Column("changed_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("arrival_event_id",sa.String(64),sa.ForeignKey("trip_stop_arrivals.event_id",ondelete="RESTRICT")),
        sa.UniqueConstraint("trip_id","scope_key",name="pickup_visit_once"),
        sa.CheckConstraint("state IN ('SCHEDULED','ARRIVED','WAITING','PICKED_UP','MISSED','CANCELLED')",name="pickup_window_state"),
        sa.CheckConstraint("(mode='production' AND duration_seconds=900) OR (mode='simulation_demo' AND duration_seconds BETWEEN 5 AND 120)",name="pickup_duration_mode"),
        sa.CheckConstraint("(started_at IS NULL AND deadline_at IS NULL) OR (started_at IS NOT NULL AND deadline_at > started_at)",name="pickup_deadline_pair"))
    op.create_index("pickup_expiry_due","pickup_windows",["deadline_at","id"],postgresql_where=sa.text("state = 'WAITING'"))
    op.create_table("pickup_outcomes",
        sa.Column("window_id",sa.String(64),sa.ForeignKey("pickup_windows.id",ondelete="RESTRICT"),primary_key=True),
        sa.Column("student_id",sa.String(64),primary_key=True),
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("stop_sequence",sa.Integer(),nullable=False),sa.Column("student_name",sa.String(200),nullable=False),
        sa.Column("state",sa.String(16),nullable=False),sa.Column("changed_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("picked_up_at",sa.DateTime(timezone=True)),sa.Column("action_source",sa.String(48),nullable=False),
        sa.UniqueConstraint("trip_id","student_id",name="pickup_student_once"),sa.UniqueConstraint("trip_id","stop_sequence",name="pickup_stop_once"),
        sa.CheckConstraint("state IN ('SCHEDULED','ARRIVED','WAITING','PICKED_UP','MISSED','CANCELLED')",name="pickup_outcome_state"))
    op.create_table("pickup_transitions",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("window_id",sa.String(64),sa.ForeignKey("pickup_windows.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("student_id",sa.String(64)),sa.Column("from_state",sa.String(16)),sa.Column("to_state",sa.String(16),nullable=False),
        sa.Column("effective_at",sa.DateTime(timezone=True),nullable=False),sa.Column("recorded_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("action_source",sa.String(48),nullable=False),sa.Column("reason",sa.String(500),nullable=False))
    op.create_index("pickup_transition_history","pickup_transitions",["window_id","recorded_at","id"])


def downgrade():
    raise RuntimeError("Archive pickup outcomes and audit history before removing this migration.")
