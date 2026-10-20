"""Allow truly unknown research stop ETAs without inventing timestamps."""
from alembic import op
import sqlalchemy as sa
revision='0019_research_unknown_eta'
down_revision='0018_research_observations'
branch_labels=None
depends_on=None
def upgrade():
    op.alter_column('route_stops','eta_seconds',existing_type=sa.Integer(),nullable=True)
def downgrade():
    # Fails transactionally if unknown-ETA research stops exist; never fill fake ETAs.
    op.alter_column('route_stops','eta_seconds',existing_type=sa.Integer(),nullable=False)
