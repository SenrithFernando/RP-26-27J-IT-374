"""Persistent trips pinned to immutable saved route versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "0006_trip_lifecycle"
down_revision = "0005_auto_planning"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("route_execution_status", "route_versions", type_="check")
    op.create_check_constraint("route_execution_status", "route_versions", "execution_status IN ('pre_trip', 'active', 'completed', 'cancelled')")
    op.create_table("trips",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("route_id", sa.String(64), sa.ForeignKey("route_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("vehicle_id", sa.String(64), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.String(500)),
        sa.Column("unfinished_actions", JSONB(), nullable=False),
        sa.CheckConstraint("state IN ('PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED')", name="trip_state"),
        sa.CheckConstraint("direction IN ('morning', 'afternoon')", name="trip_direction"),
        sa.CheckConstraint("(state = 'PLANNED' AND started_at IS NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (state = 'ACTIVE' AND started_at IS NOT NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (state = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND cancelled_at IS NULL) OR (state = 'CANCELLED' AND cancelled_at IS NOT NULL AND completed_at IS NULL AND cancellation_reason IS NOT NULL)", name="trip_timestamps"))
    op.create_index("one_active_trip_per_vehicle", "trips", ["vehicle_id"], unique=True, postgresql_where=sa.text("state = 'ACTIVE'"))
    op.create_index("one_open_trip_per_route", "trips", ["route_id"], unique=True, postgresql_where=sa.text("state IN ('PLANNED', 'ACTIVE')"))


def downgrade():
    # Do not rewrite cancelled snapshots or discard trip history implicitly.
    raise RuntimeError("Trip history requires an explicit archival plan before downgrade.")
