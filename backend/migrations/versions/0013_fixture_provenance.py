"""Append-only fixture provenance and auditable source corrections; no data rewrite."""
from alembic import op
import sqlalchemy as sa

revision = "0013_fixture_provenance"
down_revision = "0012_operational_episodes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("synthetic_trip_provenance",
        sa.Column("trip_id", sa.String(64), sa.ForeignKey("trips.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("generator", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("provenance_corrections",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("entity_table", sa.String(64), nullable=False),
        sa.Column("entity_key", sa.String(200), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("previous_source", sa.String(48), nullable=False),
        sa.Column("corrected_source", sa.String(48), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correction_code", sa.String(80), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entity_table", "entity_key", "field_name", "correction_code", name="provenance_correction_once"))
    op.execute("""CREATE FUNCTION preserve_provenance_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Provenance history is append-only'; END; $$""")
    for table in ("provenance_corrections", "synthetic_trip_provenance"):
        op.execute(f"CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION preserve_provenance_history()")


def downgrade():
    op.drop_table("provenance_corrections")
    op.drop_table("synthetic_trip_provenance")
    op.execute("DROP FUNCTION preserve_provenance_history()")
