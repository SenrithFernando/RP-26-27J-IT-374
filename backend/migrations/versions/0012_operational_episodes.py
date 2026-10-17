"""Preliminary operational deviation/low-movement episodes, not safety diagnoses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision="0012_operational_episodes"
down_revision="0011_missed_pickup_notifications"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("trip_operational_monitors",
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),primary_key=True),
        sa.Column("route_id",sa.String(64),sa.ForeignKey("route_versions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("settings",JSONB(),nullable=False),sa.Column("geometry",JSONB(),nullable=False),sa.Column("progress",JSONB(),nullable=False),
        sa.Column("last_recorded_at",sa.DateTime(timezone=True)),sa.Column("last_source",sa.String(24)))
    op.create_table("operational_episodes",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("route_id",sa.String(64),sa.ForeignKey("route_versions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("kind",sa.String(32),nullable=False),sa.Column("episode",sa.Integer(),nullable=False),sa.Column("status",sa.String(16),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("confirmed_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("recovered_at",sa.DateTime(timezone=True)),sa.Column("closed_at",sa.DateTime(timezone=True)),sa.Column("recovery_reason",sa.String(200)),
        sa.Column("source",sa.String(24),nullable=False),sa.Column("recovery_source",sa.String(24)),
        sa.Column("geometry_quality",sa.String(40),nullable=False),sa.Column("geometry_source",sa.String(32),nullable=False),
        sa.Column("thresholds",JSONB(),nullable=False),sa.Column("evidence",JSONB(),nullable=False),
        sa.Column("confirming_position_id",sa.String(64),sa.ForeignKey("vehicle_positions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("recovery_position_id",sa.String(64),sa.ForeignKey("vehicle_positions.id",ondelete="RESTRICT")),
        sa.UniqueConstraint("trip_id","kind","episode",name="operational_episode_identity"),
        sa.CheckConstraint("kind IN ('route_deviation','unexpected_stop')",name="operational_episode_kind"),
        sa.CheckConstraint("status IN ('ACTIVE','RECOVERED','CLOSED')",name="operational_episode_status"))
    op.create_index("operational_one_active_kind","operational_episodes",["trip_id","kind"],unique=True,postgresql_where=sa.text("status='ACTIVE'"))
    op.create_index("operational_trip_history","operational_episodes",["trip_id",sa.text("confirmed_at DESC"),"id"])


def downgrade():
    raise RuntimeError("Archive operational episodes before removing monitoring history.")
