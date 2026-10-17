"""Order transitions even when effective/recorded timestamps coincide."""
from alembic import op
import sqlalchemy as sa
revision="0010_pickup_audit_order"
down_revision="0009_pickup_windows"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("pickup_transitions",sa.Column("order_id",sa.BigInteger(),sa.Identity(),nullable=False))
    op.create_unique_constraint("pickup_transition_order_unique","pickup_transitions",["order_id"])
    op.create_index("pickup_history_order","pickup_transitions",["window_id","order_id"])

def downgrade():
    raise RuntimeError("Archive pickup transition history before downgrade.")
