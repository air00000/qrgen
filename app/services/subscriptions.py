import json
import logging
from datetime import datetime, timedelta, timezone

from app.services import db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dur(plan_type: str) -> timedelta:
    if plan_type == "day":
        return timedelta(days=1)
    if plan_type == "week":
        return timedelta(weeks=1)
    raise ValueError("unknown plan")


def has_active_subscription(user_id: int) -> bool:
    row = db.fetchone(
        """
        SELECT 1
        FROM subscriptions
        WHERE user_id = ? AND is_active = 1 AND ends_at > CURRENT_TIMESTAMP
        ORDER BY ends_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    return bool(row)


def get_subscription_status(user_id: int):
    return db.fetchone(
        """
        SELECT plan_type, starts_at, ends_at
        FROM subscriptions
        WHERE user_id = ? AND is_active = 1
        ORDER BY ends_at DESC
        LIMIT 1
        """,
        (user_id,),
    )


def create_pending_payment(payment_id, user_id: int, plan_type: str, amount_usdt: float, invoice_id=None):
    db.execute(
        """
        INSERT INTO payments(payment_id, user_id, plan_type, amount_usdt, invoice_id, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        ON CONFLICT(payment_id) DO NOTHING
        """,
        (payment_id, user_id, plan_type, amount_usdt, invoice_id),
    )


def activate_payment(payment_id: str, raw_payload: dict) -> bool:
    """Idempotent payment activation by payment_id."""

    def _tx(conn):
        row = conn.execute(
            "SELECT payment_id, user_id, plan_type, status FROM payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()
        if not row:
            raise ValueError("payment not found")

        if row["status"] == "paid":
            return False

        now = _now()
        payload_json = json.dumps(raw_payload, ensure_ascii=False)
        conn.execute(
            """
            UPDATE payments
            SET status='paid', paid_at=CURRENT_TIMESTAMP, raw_payload=?, updated_at=CURRENT_TIMESTAMP
            WHERE payment_id = ?
            """,
            (payload_json, payment_id),
        )

        active = conn.execute(
            """
            SELECT id, ends_at
            FROM subscriptions
            WHERE user_id = ? AND is_active = 1
            ORDER BY ends_at DESC
            LIMIT 1
            """,
            (row["user_id"],),
        ).fetchone()

        base = now
        if active:
            ends_at = datetime.fromisoformat(active["ends_at"].replace("Z", "+00:00"))
            if ends_at > now:
                base = ends_at
            conn.execute("UPDATE subscriptions SET is_active = 0, updated_at=CURRENT_TIMESTAMP WHERE user_id = ?", (row["user_id"],))

        start_at = now
        end_at = base + _dur(row["plan_type"])
        conn.execute(
            """
            INSERT INTO subscriptions(user_id, plan_type, starts_at, ends_at, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                row["user_id"],
                row["plan_type"],
                start_at.isoformat(),
                end_at.isoformat(),
            ),
        )
        logger.info("Subscription activated: user=%s plan=%s until=%s", row["user_id"], row["plan_type"], end_at.isoformat())
        return True

    return db.transaction(_tx)
