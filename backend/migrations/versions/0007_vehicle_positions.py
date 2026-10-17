"""Timestamped source-labelled vehicle positions."""
from alembic import op
import sqlalchemy as sa
revision = "0007_vehicle_positions"
down_revision = "0006_trip_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vehicle_positions",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("sample_id",sa.String(128),nullable=False),
        sa.Column("vehicle_id",sa.String(64),sa.ForeignKey("vehicles.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT")),
        sa.Column("source",sa.String(24),nullable=False),
        sa.Column("latitude",sa.Float(),nullable=False),sa.Column("longitude",sa.Float(),nullable=False),
        sa.Column("speed_mps",sa.Float()),
        sa.Column("recorded_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("received_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("vehicle_id","source","sample_id",name="position_sample_identity"),
        sa.UniqueConstraint("vehicle_id","recorded_at",name="position_vehicle_timestamp"),
        sa.CheckConstraint("source IN ('simulation','actual_device')",name="position_source"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",name="position_coordinates"),
        sa.CheckConstraint("speed_mps IS NULL OR (speed_mps >= 0 AND speed_mps < 'Infinity'::float8)",name="position_speed"))
    op.create_index("positions_vehicle_recorded","vehicle_positions",["vehicle_id",sa.text("recorded_at DESC"),"id"])
    op.create_index("positions_trip_recorded","vehicle_positions",["trip_id",sa.text("recorded_at DESC"),"id"])


def downgrade():
    op.drop_table("vehicle_positions")
