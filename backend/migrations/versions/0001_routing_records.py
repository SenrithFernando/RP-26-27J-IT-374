"""Initial persistent routing records; no synthetic observations or predictions."""
from alembic import op
import sqlalchemy as sa

revision = "0001_routing_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("schools",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("input_source", sa.String(32), nullable=False),
        sa.CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="school_source"))
    op.create_table("vehicles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("input_source", sa.String(32), nullable=False),
        sa.CheckConstraint("capacity > 0", name="vehicle_capacity_positive"),
        sa.CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="vehicle_source"))
    op.create_table("students",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("home_id", sa.String(64), nullable=False),
        sa.Column("school_id", sa.String(64), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("vehicle_id", sa.String(64), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("input_source", sa.String(32), nullable=False),
        sa.CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="student_source"))
    op.create_index("ix_students_school_id", "students", ["school_id"])
    op.create_index("ix_students_vehicle_id", "students", ["vehicle_id"])


def downgrade():
    op.drop_table("students")
    op.drop_table("vehicles")
    op.drop_table("schools")
