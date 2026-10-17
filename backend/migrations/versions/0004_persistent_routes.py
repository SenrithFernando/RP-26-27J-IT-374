"""School schedules and immutable generated route versions/stops."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0004_persistent_routes"
down_revision = "0003_confirmed_locations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("schools", sa.Column("morning_deadline_seconds", sa.Integer(), nullable=True))
    op.add_column("schools", sa.Column("afternoon_finish_seconds", sa.Integer(), nullable=True))
    op.create_check_constraint("school_morning_deadline_range", "schools", "morning_deadline_seconds BETWEEN 0 AND 86399")
    op.create_check_constraint("school_afternoon_finish_range", "schools", "afternoon_finish_seconds BETWEEN 0 AND 86399")
    op.create_table("route_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("vehicle_id", sa.String(64), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("departure_seconds", sa.Integer(), nullable=False),
        sa.Column("feasibility_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_settings", postgresql.JSONB(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("vehicle_id", "direction", "version", name="uq_route_vehicle_direction_version"),
        sa.CheckConstraint("version > 0", name="route_version_positive"),
        sa.CheckConstraint("direction IN ('morning', 'afternoon')", name="route_direction"))
    op.create_table("route_stops",
        sa.Column("route_id", sa.String(64), sa.ForeignKey("route_versions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("student_id", sa.String(64), nullable=True),
        sa.Column("location_id", sa.String(128), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("eta_seconds", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("sequence > 0", name="route_stop_sequence_positive"),
        sa.CheckConstraint("action IN ('start', 'pickup', 'delivery', 'end')", name="route_stop_action"))
    op.create_index("ix_route_stops_student_id", "route_stops", ["student_id"])


def downgrade():
    op.drop_table("route_stops")
    op.drop_table("route_versions")
    op.drop_constraint("school_morning_deadline_range", "schools", type_="check")
    op.drop_constraint("school_afternoon_finish_range", "schools", type_="check")
    op.drop_column("schools", "morning_deadline_seconds")
    op.drop_column("schools", "afternoon_finish_seconds")
