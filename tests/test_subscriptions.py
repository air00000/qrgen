import os
import tempfile
import unittest

from app.config import CFG
from app.services import db
from app.services.subscriptions import (
    activate_payment,
    create_pending_payment,
    has_active_subscription,
)


class TestSubscriptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        CFG.APP_DB_PATH = os.path.join(self.tmp.name, "app.db")
        db.run_migrations()

    def tearDown(self):
        self.tmp.cleanup()

    def test_activation_idempotent(self):
        payment_id = "p-1"
        create_pending_payment(payment_id, 123, "day", 5.0, "inv-1")

        first = activate_payment(payment_id, {"status": "paid"})
        second = activate_payment(payment_id, {"status": "paid"})

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(has_active_subscription(123))


if __name__ == "__main__":
    unittest.main()
