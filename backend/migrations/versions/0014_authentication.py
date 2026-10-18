"""Accounts, scoped relationships, revocable opaque login/tracking sessions."""
from alembic import op
import sqlalchemy as sa
revision="0014_authentication"
down_revision="0013_fixture_provenance"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('accounts',sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('username',sa.String(100),unique=True,nullable=False),sa.Column('password_hash',sa.String(500),nullable=False),
        sa.Column('role',sa.String(16),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),
        sa.Column('demo_only',sa.Boolean(),nullable=False),sa.Column('failed_attempts',sa.Integer(),nullable=False),
        sa.Column('locked_until',sa.DateTime(timezone=True)),sa.CheckConstraint("role IN ('administrator','driver','parent')",name='account_role'))
    op.create_table('driver_vehicles',sa.Column('account_id',sa.String(64),sa.ForeignKey('accounts.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('vehicle_id',sa.String(64),sa.ForeignKey('vehicles.id',ondelete='RESTRICT'),primary_key=True))
    op.create_table('parent_students',sa.Column('account_id',sa.String(64),sa.ForeignKey('accounts.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('student_id',sa.String(64),sa.ForeignKey('students.id',ondelete='RESTRICT'),primary_key=True))
    op.create_table('login_sessions',sa.Column('id',sa.String(64),primary_key=True),sa.Column('token_hash',sa.String(64),unique=True,nullable=False),
        sa.Column('account_id',sa.String(64),sa.ForeignKey('accounts.id',ondelete='RESTRICT'),nullable=False),sa.Column('mode',sa.String(8),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('revoked_at',sa.DateTime(timezone=True)),sa.CheckConstraint("mode IN ('demo','real')",name='login_mode'))
    op.create_index('ix_login_sessions_account_id','login_sessions',['account_id']);op.create_index('ix_login_sessions_expires_at','login_sessions',['expires_at'])
    op.create_table('tracking_sessions',sa.Column('id',sa.String(64),primary_key=True),sa.Column('token_hash',sa.String(64),unique=True,nullable=False),
        sa.Column('login_session_id',sa.String(64),sa.ForeignKey('login_sessions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('vehicle_id',sa.String(64),sa.ForeignKey('vehicles.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('trip_id',sa.String(64),sa.ForeignKey('trips.id',ondelete='RESTRICT'),nullable=False),sa.Column('kind',sa.String(16),nullable=False),
        sa.Column('label',sa.String(100),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('revoked_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('phone','simulation')",name='tracking_kind'))
    for column in ['login_session_id','vehicle_id','trip_id']:op.create_index('ix_tracking_sessions_'+column,'tracking_sessions',[column])


def downgrade():
    for table in ['tracking_sessions','login_sessions','parent_students','driver_vehicles','accounts']:op.drop_table(table)
