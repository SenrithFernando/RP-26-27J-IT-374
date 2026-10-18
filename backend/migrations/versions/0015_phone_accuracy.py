"""Phone accuracy and server-derived device-session lineage; preserve old samples."""
from alembic import op
import sqlalchemy as sa
revision='0015_phone_accuracy'
down_revision='0014_authentication'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('vehicle_positions',sa.Column('accuracy_m',sa.Float(),nullable=True))
    op.add_column('vehicle_positions',sa.Column('tracking_session_id',sa.String(64),nullable=True))
    op.create_foreign_key('position_tracking_session','vehicle_positions','tracking_sessions',['tracking_session_id'],['id'],ondelete='RESTRICT')
    op.create_check_constraint('position_accuracy','vehicle_positions',"accuracy_m IS NULL OR (accuracy_m >= 0 AND accuracy_m < 'Infinity'::float8)")

def downgrade():
    op.drop_constraint('position_accuracy','vehicle_positions',type_='check')
    op.drop_constraint('position_tracking_session','vehicle_positions',type_='foreignkey')
    op.drop_column('vehicle_positions','tracking_session_id')
    op.drop_column('vehicle_positions','accuracy_m')
