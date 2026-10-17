"""One persistent in-app missed event per trip/student pickup."""
from alembic import op
import sqlalchemy as sa
revision="0011_missed_pickup_notifications"
down_revision="0010_pickup_audit_order"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("missed_pickup_notifications",
        sa.Column("id",sa.String(64),primary_key=True),sa.Column("order_id",sa.BigInteger(),sa.Identity(),nullable=False),
        sa.Column("kind",sa.String(32),nullable=False),
        sa.Column("trip_id",sa.String(64),sa.ForeignKey("trips.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("window_id",sa.String(64),nullable=False),sa.Column("student_id",sa.String(64),nullable=False),
        sa.Column("student_name",sa.String(200),nullable=False),
        sa.Column("vehicle_id",sa.String(64),sa.ForeignKey("vehicles.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("route_id",sa.String(64),nullable=False),sa.Column("stop_sequence",sa.Integer(),nullable=False),
        sa.Column("occurred_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("action_source",sa.String(48),nullable=False),sa.Column("position_source",sa.String(24)),
        sa.Column("mode",sa.String(24),nullable=False),sa.Column("delivery_status",sa.String(32),nullable=False),
        sa.Column("message",sa.String(500),nullable=False),
        sa.Column("admin_read_at",sa.DateTime(timezone=True)),sa.Column("parent_read_at",sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id",name="missed_notification_order"),
        sa.UniqueConstraint("trip_id","student_id","kind",name="one_missed_notification_per_pickup"),
        sa.ForeignKeyConstraint(["window_id","student_id"],["pickup_outcomes.window_id","pickup_outcomes.student_id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id","stop_sequence"],["route_stops.route_id","route_stops.sequence"],ondelete="RESTRICT"),
        sa.CheckConstraint("kind='missed_pickup'",name="missed_notification_kind"),
        sa.CheckConstraint("delivery_status='in_app_event_created'",name="missed_notification_delivery"))
    op.create_index("missed_notification_student_order","missed_pickup_notifications",["student_id",sa.text("order_id DESC")])
    op.create_index("missed_notification_admin_unread","missed_pickup_notifications",["order_id"],postgresql_where=sa.text("admin_read_at IS NULL"))
    op.create_index("missed_notification_parent_unread","missed_pickup_notifications",["student_id","order_id"],postgresql_where=sa.text("parent_read_at IS NULL"))


def downgrade():
    raise RuntimeError("Archive notification events/read state before removing this migration.")
