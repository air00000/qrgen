This module will host service generators (markt/subito/wallapop/etc.).

rust-only branch goal:
- all image generation happens here (Rust)
- Python becomes a thin client calling POST /generate
- /qr endpoint must not exist
