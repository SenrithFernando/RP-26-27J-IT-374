"""Student coordinates and non-destructive deactivation."""
from alembic import op
import sqlalchemy as sa

revision = "0002_student_management"
down_revision = "0001_routing_records"
branch_labels = None
depends_on = None


def upgrade():
    # Existing synthetic students have unknown coordinates; never invent them.
    op.add_column("students", sa.Column("home_latitude", sa.Float(), nullable=True))
    op.add_column("students", sa.Column("home_longitude", sa.Float(), nullable=True))
    op.add_column("students", sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_check_constraint("student_latitude_range", "students", "home_latitude BETWEEN -90 AND 90")
    op.create_check_constraint("student_longitude_range", "students", "home_longitude BETWEEN -180 AND 180")
    op.create_check_constraint("student_coordinates_pair", "students", "(home_latitude IS NULL) = (home_longitude IS NULL)")


def downgrade():
    op.drop_constraint("student_coordinates_pair", "students", type_="check")
    op.drop_constraint("student_longitude_range", "students", type_="check")
    op.drop_constraint("student_latitude_range", "students", type_="check")
    op.drop_column("students", "active")
    op.drop_column("students", "home_longitude")
    op.drop_column("students", "home_latitude")
