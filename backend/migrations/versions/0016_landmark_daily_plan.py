"""Isolated Malabe scenario, dated inputs and publication; no historical rewrites."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0016_landmark_daily_plan'
down_revision='0015_phone_accuracy'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('landmark_scenarios',sa.Column('id',sa.String(64),primary_key=True),sa.Column('vehicle_id',sa.String(64),sa.ForeignKey('vehicles.id'),unique=True,nullable=False),sa.Column('default_date',sa.Date(),nullable=False),sa.Column('policy',JSONB,nullable=False))
    for table,fields,check in [('landmark_attendance',['am','pm'],"am IN ('yes','no','unknown') AND pm IN ('yes','no','unknown')"),('landmark_boarding',['outcome'],"outcome IN ('boarded','no_show','unknown')")]:
        op.create_table(table,sa.Column('scenario_id',sa.String(64),sa.ForeignKey('landmark_scenarios.id'),primary_key=True),sa.Column('service_date',sa.Date(),primary_key=True),sa.Column('student_id',sa.String(64),sa.ForeignKey('students.id'),primary_key=True),*[sa.Column(f,sa.String(12),nullable=False) for f in fields],sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),sa.Column('event_id',sa.String(128),nullable=False),sa.CheckConstraint(check,name=table+'_values'))
    op.create_table('landmark_input_events',sa.Column('event_id',sa.String(128),primary_key=True),sa.Column('scenario_id',sa.String(64),sa.ForeignKey('landmark_scenarios.id'),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),sa.Column('payload',JSONB,nullable=False),sa.Column('actor_id',sa.String(64),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('landmark_daily_plans',sa.Column('scenario_id',sa.String(64),sa.ForeignKey('landmark_scenarios.id'),primary_key=True),sa.Column('service_date',sa.Date(),primary_key=True),sa.Column('direction',sa.String(16),primary_key=True),sa.Column('route_id',sa.String(64),sa.ForeignKey('route_versions.id')),sa.Column('publication',sa.String(16),nullable=False),sa.Column('review',JSONB,nullable=False))
def downgrade():
    for t in ['landmark_daily_plans','landmark_input_events','landmark_boarding','landmark_attendance','landmark_scenarios']:op.drop_table(t)
