import logging
import requests

from app.config import CFG

logger = logging.getLogger(__name__)


class CryptoBotError(Exception):
    pass


def _headers() -> dict:
    if not CFG.CRYPTOBOT_API_TOKEN:
        raise CryptoBotError("CryptoBot token is not configured")
    return {"Crypto-Pay-API-Token": CFG.CRYPTOBOT_API_TOKEN}


def create_invoice(payment_id: str, amount: float, description: str) -> dict:
    url = f"{CFG.CRYPTOBOT_API_BASE.rstrip('/')}/createInvoice"
    payload = {
        "asset": "USDT",
        "amount": f"{amount:.2f}",
        "description": description,
        "payload": payment_id,
    }
    r = requests.post(url, headers=_headers(), json=payload, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise CryptoBotError(str(data))
    return data["result"]


def get_invoice(invoice_id: str):
    url = f"{CFG.CRYPTOBOT_API_BASE.rstrip('/')}/getInvoices"
    r = requests.get(url, headers=_headers(), params={"invoice_ids": invoice_id}, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise CryptoBotError(str(data))
    items = data.get("result", {}).get("items", [])
    return items[0] if items else None
