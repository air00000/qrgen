import os
import tempfile
import unittest

from app.config import CFG
from app.services import db


class TestPaymentsStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        CFG.APP_DB_PATH = os.path.join(self.tmp.name, "app.db")
        db.run_migrations()

    def tearDown(self):
        self.tmp.cleanup()

    def test_payment_id_unique(self):
        db.execute(
            "INSERT INTO payments(payment_id, user_id, plan_type, amount_usdt, status) VALUES (?, ?, ?, ?, ?)",
            ("same-id", 1, "day", 5.0, "pending"),
        )
        with self.assertRaises(Exception):
            db.execute(
                "INSERT INTO payments(payment_id, user_id, plan_type, amount_usdt, status) VALUES (?, ?, ?, ?, ?)",
                ("same-id", 2, "week", 20.0, "pending"),
            )


if __name__ == "__main__":
    unittest.main()
