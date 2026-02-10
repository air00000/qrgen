"""app/bridge_generate.py

CLI bridge used by the Rust backend.

It reads a UniversalRequest-like JSON from stdin and writes PNG bytes to stdout.

Exit codes:
- 0: ok (stdout = png bytes)
- 2: bad request / generation error (stderr contains message)
- 1: internal error (stderr contains message)

This lets the Rust backend keep the API contract 1:1 while the heavy image
composition logic is still implemented in Python.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict


def _read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.buffer.read()
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON input: {e}")


def main() -> int:
    try:
        req = _read_stdin_json()

        country = (req.get("country") or "").lower()
        service = (req.get("service") or "").lower()
        method = (req.get("method") or "").lower()

        data = {
            "title": req.get("title"),
            "price": req.get("price"),
            "url": req.get("url"),
            "photo": req.get("photo"),
            "name": req.get("name"),
            "address": req.get("address"),
            "seller_name": req.get("seller_name"),
            "seller_photo": req.get("seller_photo"),
        }

        # Import routing from the existing FastAPI implementation.
        # NOTE: This module has side effects (imports PIL, fonts, etc.)
        from app.api import GEO_CONFIG, _route_generation

        if country not in GEO_CONFIG:
            raise ValueError(f"Unknown country: {country}. Available: {list(GEO_CONFIG.keys())}")
        if service not in GEO_CONFIG[country]["services"]:
            raise ValueError(
                f"Unknown service '{service}' for country '{country}'. "
                f"Available: {list(GEO_CONFIG[country]['services'].keys())}"
            )
        methods = GEO_CONFIG[country]["services"][service]["methods"]
        if method not in methods:
            raise ValueError(
                f"Unknown method '{method}' for service '{service}'. Available: {list(methods.keys())}"
            )

        png_bytes = _route_generation(country, service, method, data)
        if not isinstance(png_bytes, (bytes, bytearray)):
            raise RuntimeError("Generator returned non-bytes result")

        sys.stdout.buffer.write(png_bytes)
        return 0

    except Exception as e:
        # Map known generation errors to "bad request".
        try:
            from app.services.pdf import PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError
            from app.services.twodehands import DehandsGenerationError
            from app.services.kleize import KleizeGenerationError
            from app.services.conto import ContoGenerationError
            from app.services.depop import DepopGenerationError
            from app.services.depop_variants import DepopVariantError
            from app.services.markt import MarktGenerationError

            bad_types = (
                ValueError,
                PDFGenerationError,
                FigmaNodeNotFoundError,
                QRGenerationError,
                DehandsGenerationError,
                KleizeGenerationError,
                ContoGenerationError,
                DepopGenerationError,
                DepopVariantError,
                MarktGenerationError,
            )
            is_bad = isinstance(e, bad_types)
        except Exception:
            is_bad = isinstance(e, ValueError)

        sys.stderr.write(str(e))
        sys.stderr.write("\n")
        return 2 if is_bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
