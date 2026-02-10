import os
import tempfile
import unittest
from unittest import mock


class TestQRTigerClient(unittest.TestCase):
    def test_generate_qr_saves_png(self):
        from app.services import qrtiger

        fake_png = b"\x89PNG\r\n\x1a\n" + b"data"

        with tempfile.TemporaryDirectory() as td:
            with mock.patch("app.services.qrtiger.requests.post") as mpost:
                mpost.return_value.status_code = 200
                mpost.return_value.content = fake_png

                path = qrtiger.generate_qr("https://example.com", td)

                self.assertTrue(os.path.exists(path))
                with open(path, "rb") as f:
                    self.assertTrue(f.read().startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
