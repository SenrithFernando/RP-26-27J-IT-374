"""Confirmed addresses and coordinates; unknown locations stay unknown."""
from alembic import op
import sqlalchemy as sa
revision = "0003_confirmed_locations"
down_revision = "0002_student_management"
branch_labels = None
depends_on = None


def location_columns(table, prefix, confirmed, method):
    for name, column_type, default in (
        (prefix + "address", sa.String(500), ""),
        (prefix + "latitude", sa.Float(), None),
        (prefix + "longitude", sa.Float(), None),
        (confirmed, sa.Boolean(), sa.false()),
        (method, sa.String(32), "manual"),
    ):
        op.add_column(table, sa.Column(name, column_type, nullable=default is None, server_default=default))


def upgrade():
    location_columns("schools", "", "location_confirmed", "location_method")
    op.create_check_constraint("school_coordinate_range", "schools", "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180")
    op.create_check_constraint("school_coordinates_pair", "schools", "(latitude IS NULL) = (longitude IS NULL)")
    op.create_check_constraint("school_confirmed_location", "schools", "NOT location_confirmed OR (latitude IS NOT NULL AND longitude IS NOT NULL AND length(trim(address)) > 0)")
    for position in ("start", "end"):
        location_columns("vehicles", position + "_", position + "_confirmed", position + "_method")
        op.create_check_constraint(f"vehicle_{position}_coordinate_range", "vehicles", f"{position}_latitude BETWEEN -90 AND 90 AND {position}_longitude BETWEEN -180 AND 180")
        op.create_check_constraint(f"vehicle_{position}_coordinates_pair", "vehicles", f"({position}_latitude IS NULL) = ({position}_longitude IS NULL)")
        op.create_check_constraint(f"vehicle_{position}_confirmed_location", "vehicles", f"NOT {position}_confirmed OR ({position}_latitude IS NOT NULL AND {position}_longitude IS NOT NULL AND length(trim({position}_address)) > 0)")
    op.add_column("students", sa.Column("home_address", sa.String(500), nullable=False, server_default=""))
    op.add_column("students", sa.Column("location_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("students", sa.Column("location_method", sa.String(32), nullable=False, server_default="manual"))
    op.create_check_constraint("student_confirmed_location", "students", "NOT location_confirmed OR (home_latitude IS NOT NULL AND home_longitude IS NOT NULL AND length(trim(home_address)) > 0)")


def downgrade():
    op.drop_constraint("student_confirmed_location", "students", type_="check")
    for column in ("home_address", "location_confirmed", "location_method"):
        op.drop_column("students", column)
    for position in ("start", "end"):
        for suffix in ("coordinate_range", "coordinates_pair", "confirmed_location"):
            op.drop_constraint(f"vehicle_{position}_{suffix}", "vehicles", type_="check")
        for suffix in ("address", "latitude", "longitude", "confirmed", "method"):
            op.drop_column("vehicles", f"{position}_{suffix}")
    for name in ("school_coordinate_range", "school_coordinates_pair", "school_confirmed_location"):
        op.drop_constraint(name, "schools", type_="check")
    for column in ("address", "latitude", "longitude", "location_confirmed", "location_method"):
        op.drop_column("schools", column)
