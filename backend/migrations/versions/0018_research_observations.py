"""Separate reviewed research observations from provider estimates and raw GPS."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0018_research_observations'
down_revision='0017_grouped_pickup_outcomes'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('research_collections',
        sa.Column('trip_id',sa.String(64),sa.ForeignKey('trips.id'),primary_key=True),
        sa.Column('dataset',sa.String(40),nullable=False),sa.Column('protocol',JSONB,nullable=False),
        sa.Column('actor_id',sa.String(64),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("dataset IN ('synthetic','stationary_adult_phone','moving_adult_landmark','authorized_operational')",name='research_dataset'))
    op.create_table('travel_observations',
        sa.Column('id',sa.String(64),primary_key=True),sa.Column('family_id',sa.String(64),nullable=False),
        sa.Column('revision',sa.Integer,nullable=False),sa.Column('previous_id',sa.String(64),sa.ForeignKey('travel_observations.id')),
        sa.Column('trip_id',sa.String(64),sa.ForeignKey('research_collections.trip_id'),nullable=False),
        sa.Column('route_id',sa.String(64),sa.ForeignKey('route_versions.id'),nullable=False),
        sa.Column('dataset',sa.String(40),nullable=False),sa.Column('status',sa.String(12),nullable=False),
        sa.Column('raw',JSONB,nullable=False),sa.Column('analysis',JSONB,nullable=False),
        sa.Column('actor_id',sa.String(64),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('family_id','revision',name='observation_revision_once'),
        sa.CheckConstraint("status IN ('pending','accepted','rejected')",name='observation_status'))
    op.create_index('observation_trip_family','travel_observations',['trip_id','family_id','revision'])
    op.create_table('segment_estimates',sa.Column('observation_id',sa.String(64),sa.ForeignKey('travel_observations.id'),primary_key=True),
        sa.Column('snapshot',JSONB,nullable=False))

def downgrade():
    op.drop_table('segment_estimates')
    op.drop_index('observation_trip_family',table_name='travel_observations')
    op.drop_table('travel_observations')
    op.drop_table('research_collections')
