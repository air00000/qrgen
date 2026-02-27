import io
import unittest

from PIL import Image

from app.services.watermark import apply_enclave_watermark


class TestWatermark(unittest.TestCase):
    def test_apply_watermark_png(self):
        img = Image.new("RGB", (400, 300), color=(255, 255, 255))
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        raw = bio.getvalue()

        out = apply_enclave_watermark(raw)
        self.assertTrue(out.startswith(b"\x89PNG"))
        self.assertNotEqual(raw, out)


if __name__ == "__main__":
    unittest.main()
