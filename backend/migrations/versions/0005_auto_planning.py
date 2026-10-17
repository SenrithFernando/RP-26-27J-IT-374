"""Durable roster events, plan freshness and protected execution snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "0005_auto_planning"
down_revision = "0004_persistent_routes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vehicles", sa.Column("roster_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("routing_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=True, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("affected_vehicles", JSONB(), nullable=False),
        sa.Column("record_snapshot", JSONB(), nullable=False),
        sa.Column("before_routes", JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("outcome", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("route_versions", sa.Column("roster_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("route_versions", sa.Column("trigger_event_id", sa.String(64), sa.ForeignKey("routing_events.id"), nullable=True))
    op.add_column("route_versions", sa.Column("trigger_event_type", sa.String(64), nullable=False, server_default="manual_generation"))
    op.add_column("route_versions", sa.Column("execution_status", sa.String(16), nullable=False, server_default="pre_trip"))
    op.create_unique_constraint("uq_route_event_vehicle_direction", "route_versions", ["trigger_event_id", "vehicle_id", "direction"])
    op.create_check_constraint("route_execution_status", "route_versions", "execution_status IN ('pre_trip', 'active', 'completed')")
    op.create_table("route_plan_states",
        sa.Column("vehicle_id", sa.String(64), sa.ForeignKey("vehicles.id"), primary_key=True),
        sa.Column("direction", sa.String(16), primary_key=True),
        sa.Column("roster_version", sa.Integer(), nullable=False),
        sa.Column("generation_status", sa.String(32), nullable=False),
        sa.Column("trigger_event_id", sa.String(64), sa.ForeignKey("routing_events.id"), nullable=True),
        sa.Column("route_id", sa.String(64), sa.ForeignKey("route_versions.id"), nullable=True),
        sa.Column("settings", JSONB(), nullable=False), sa.Column("errors", JSONB(), nullable=False),
        sa.Column("comparison", JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("solver_runtime_seconds", sa.Float(), nullable=True),
        sa.CheckConstraint("direction IN ('morning', 'afternoon')", name="plan_direction"))


def downgrade():
    op.drop_table("route_plan_states")
    op.drop_constraint("uq_route_event_vehicle_direction", "route_versions", type_="unique")
    op.drop_constraint("route_execution_status", "route_versions", type_="check")
    op.drop_column("route_versions", "execution_status")
    op.drop_column("route_versions", "trigger_event_type")
    op.drop_column("route_versions", "trigger_event_id")
    op.drop_column("route_versions", "roster_version")
    op.drop_table("routing_events")
    op.drop_column("vehicles", "roster_version")
