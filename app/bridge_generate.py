"""app/bridge_generate.py

CLI bridge used by the Rust backend.

It reads a UniversalRequest-like JSON from stdin and writes PNG bytes to stdout.

Exit codes:
- 0: ok (stdout = png bytes)
- 2: bad request / generation error (stderr contains message)
- 1: internal error (stderr contains message)

This lets the Rust backend keep the API contract 1:1.
Python must NOT generate images; it only proxies to the Rust backend.
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

        # Proxy to Rust backend directly.
        from app.config import CFG
        import requests

        backend_service = service
        if backend_service == "marktplaats":
            backend_service = "markt"
        elif backend_service == "kleize":
            backend_service = "kleinanzeigen"

        payload = {
            "country": country,
            "service": backend_service,
            "method": method,
            **data,
        }

        backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
        headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}
        r = requests.post(backend_url, json=payload, headers=headers, timeout=90)
        if not r.ok:
            raise ValueError(r.text)

        sys.stdout.buffer.write(r.content)
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
