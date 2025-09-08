# app/services/cryptopay.py
import os, requests

BASE_URL = "https://pay.crypt.bot/api"
TOKEN = os.getenv("CRYPTOPAY_TOKEN")

def _headers():
    return {"Crypto-Pay-API-Token": TOKEN}

def create_invoice(asset: str, amount: float, description: str, payload: str):

    data = {
        "asset": asset,
        "amount": str(amount),
        "description": description,
        "payload": payload,
        # можно добавить expires_in, allow_comments, allow_anonymous...
    }
    r = requests.post(f"{BASE_URL}/createInvoice", headers=_headers(), json=data, timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"CryptoPay error: {j}")
    inv = j["result"]
    return {"invoice_id": str(inv["invoice_id"]), "pay_url": inv["pay_url"]}

def get_invoices(invoice_ids):
    """
    Возвращает список инвойсов с их статусом (active/paid/expired).
    """
    data = {"invoice_ids": [int(x) for x in invoice_ids]}
    r = requests.post(f"{BASE_URL}/getInvoices", headers=_headers(), json=data, timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"CryptoPay error: {j}")
    return j["result"]["items"] if "items" in j["result"] else j["result"]["invoices"]
