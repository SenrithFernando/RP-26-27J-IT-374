"""A grouped school visit retains one outcome per participant, not one per stop."""
from alembic import op
revision='0017_grouped_pickup_outcomes'
down_revision='0016_landmark_daily_plan'
branch_labels=None
depends_on=None
def upgrade():
    op.drop_constraint('pickup_stop_once','pickup_outcomes',type_='unique')
    op.create_unique_constraint('pickup_stop_once','pickup_outcomes',['trip_id','stop_sequence','student_id'])
def downgrade():
    op.drop_constraint('pickup_stop_once','pickup_outcomes',type_='unique')
    op.create_unique_constraint('pickup_stop_once','pickup_outcomes',['trip_id','stop_sequence'])
