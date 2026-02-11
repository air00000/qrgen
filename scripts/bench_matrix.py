#!/usr/bin/env python3
"""Benchmark matrix for qrgen-backend (/generate endpoint).

Outputs per-case latency stats.

Usage:
  python scripts/bench_matrix.py API_KEY --host localhost --port 8080 --iters 20 --warmup 3

Notes:
- This hits the Rust backend.
- For best results run with: RUST_LOG=perf cargo run --features perf
"""

import argparse
import statistics
import time
from typing import Any, Dict, List, Tuple

import requests


def pct(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    k = int(round((len(xs) - 1) * p))
    return xs[max(0, min(len(xs) - 1, k))]


def run_case(session: requests.Session, url: str, api_key: str, payload: Dict[str, Any], iters: int, warmup: int) -> List[float]:
    headers = {"X-API-Key": api_key}

    # warmup
    for _ in range(warmup):
        r = session.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()

    times: List[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        r = session.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        _ = r.content  # consume
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("api_key")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=3)
    args = ap.parse_args()

    endpoint = f"http://{args.host}:{args.port}/generate"

    # Minimal payloads (Rust backend ignores unknown fields)
    base = {
        "country": "it",
        "title": "MacBook Pro 2023 M3",
        "price": 1499.00,
        "photo": None,
        "name": "Mario Rossi",
        "address": "Milano, IT",
        "seller_name": "John",
        "seller_photo": None,
    }

    matrix: List[Tuple[str, Dict[str, Any]]] = [
        ("subito/qr", {**base, "service": "subito", "method": "qr", "url": "https://subito.it/test"}),
        ("subito/email_request", {**base, "service": "subito", "method": "email_request", "url": "ignored"}),
        ("subito/email_confirm", {**base, "service": "subito", "method": "email_confirm"}),
        ("subito/sms_request", {**base, "service": "subito", "method": "sms_request"}),
        ("subito/sms_confirm", {**base, "service": "subito", "method": "sms_confirm"}),

        ("depop/qr", {
            **base,
            "country": "au",
            "service": "depop",
            "method": "qr",
            "url": "https://depop.com/test",
            "seller_name": "Alice",
        }),
        ("depop/email_request", {**base, "country": "au", "service": "depop", "method": "email_request"}),
        ("depop/email_confirm", {**base, "country": "au", "service": "depop", "method": "email_confirm"}),
        ("depop/sms_request", {**base, "country": "au", "service": "depop", "method": "sms_request"}),
        ("depop/sms_confirm", {**base, "country": "au", "service": "depop", "method": "sms_confirm"}),

        ("markt/qr", {**base, "country": "de", "service": "markt", "method": "qr", "url": "https://markt.de/test"}),
        ("wallapop/qr", {**base, "country": "es", "service": "wallapop", "method": "qr", "url": "https://wallapop.com/test"}),
        ("kleinanzeigen/qr", {**base, "country": "de", "service": "kleinanzeigen", "method": "qr", "url": "https://kleinanzeigen.de/test"}),
        ("2dehands/qr", {**base, "country": "nl", "service": "2dehands", "method": "qr", "url": "https://2dehands.be/test"}),
        ("2ememain/qr", {**base, "country": "be", "service": "2ememain", "method": "qr", "url": "https://2ememain.be/test"}),
        ("conto", {**base, "country": "it", "service": "conto", "method": "default"}),
    ]

    print(f"Endpoint: {endpoint}")
    print(f"iters={args.iters} warmup={args.warmup}\n")

    with requests.Session() as s:
        for name, payload in matrix:
            times = run_case(s, endpoint, args.api_key, payload, iters=args.iters, warmup=args.warmup)
            mean = statistics.mean(times)
            med = statistics.median(times)
            p95 = pct(times, 0.95)
            print(f"{name:22s}  mean={mean:8.1f} ms  med={med:8.1f} ms  p95={p95:8.1f} ms")


if __name__ == "__main__":
    main()
