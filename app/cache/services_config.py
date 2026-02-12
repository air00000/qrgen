# app/cache/services_config.py
"""
Конфигурация всех сервисов для кеширования
"""

SERVICES_CONFIG = {
    # === MARKT (UK and NL) ===
    "markt_qr_uk":             {"display_name": "Markt QR (UK)",             "page": "Page 2", "frame": "markt1_uk", "scale": 2},
    "markt_qr_nl":             {"display_name": "Markt QR (NL)",             "page": "Page 2", "frame": "markt1_nl", "scale": 2},
    "markt_email_request_uk":  {"display_name": "Markt Email Request (UK)",  "page": "Page 2", "frame": "markt2_uk", "scale": 2},
    "markt_email_request_nl":  {"display_name": "Markt Email Request (NL)",  "page": "Page 2", "frame": "markt2_nl", "scale": 2},
    "markt_phone_request_uk":  {"display_name": "Markt Phone Request (UK)",  "page": "Page 2", "frame": "markt3_uk", "scale": 2},
    "markt_phone_request_nl":  {"display_name": "Markt Phone Request (NL)",  "page": "Page 2", "frame": "markt3_nl", "scale": 2},
    "markt_email_payment_uk":  {"display_name": "Markt Email Payment (UK)",  "page": "Page 2", "frame": "markt4_uk", "scale": 2},
    "markt_email_payment_nl":  {"display_name": "Markt Email Payment (NL)",  "page": "Page 2", "frame": "markt4_nl", "scale": 2},
    "markt_sms_payment_uk":    {"display_name": "Markt SMS Payment (UK)",    "page": "Page 2", "frame": "markt5_uk", "scale": 2},
    "markt_sms_payment_nl":    {"display_name": "Markt SMS Payment (NL)",    "page": "Page 2", "frame": "markt5_nl", "scale": 2},

    # === SUBITO (uk / nl) — фреймы subito6–10 ===
    "subito_email_request_uk": {"display_name": "Subito Email Request (UK)", "page": "Page 2", "frame": "subito6",  "scale": 2},
    "subito_email_request_nl": {"display_name": "Subito Email Request (NL)", "page": "Page 2", "frame": "subito6",  "scale": 2},
    "subito_phone_request_uk": {"display_name": "Subito Phone Request (UK)", "page": "Page 2", "frame": "subito7",  "scale": 2},
    "subito_phone_request_nl": {"display_name": "Subito Phone Request (NL)", "page": "Page 2", "frame": "subito7",  "scale": 2},
    "subito_email_payment_uk": {"display_name": "Subito Email Payment (UK)", "page": "Page 2", "frame": "subito8",  "scale": 2},
    "subito_email_payment_nl": {"display_name": "Subito Email Payment (NL)", "page": "Page 2", "frame": "subito8",  "scale": 2},
    "subito_sms_payment_uk":   {"display_name": "Subito SMS Payment (UK)",   "page": "Page 2", "frame": "subito9",  "scale": 2},
    "subito_sms_payment_nl":   {"display_name": "Subito SMS Payment (NL)",   "page": "Page 2", "frame": "subito9",  "scale": 2},
    "subito_qr_uk":            {"display_name": "Subito QR (UK)",            "page": "Page 2", "frame": "subito10", "scale": 2},
    "subito_qr_nl":            {"display_name": "Subito QR (NL)",            "page": "Page 2", "frame": "subito10", "scale": 2},

    # === WALLAPOP (Page 2) ===
    "wallapop_email_request_uk":  {"display_name": "Wallapop Email Request (UK)",  "page": "Page 2", "frame": "wallapop3_uk",  "scale": 2},
    "wallapop_email_request_es":  {"display_name": "Wallapop Email Request (ES)",  "page": "Page 2", "frame": "wallapop3_es",  "scale": 2},
    "wallapop_email_request_it":  {"display_name": "Wallapop Email Request (IT)",  "page": "Page 2", "frame": "wallapop3_it",  "scale": 2},
    "wallapop_email_request_fr":  {"display_name": "Wallapop Email Request (FR)",  "page": "Page 2", "frame": "wallapop3_fr",  "scale": 2},
    "wallapop_email_request_pr":  {"display_name": "Wallapop Email Request (PT)",  "page": "Page 2", "frame": "wallapop3_pr",  "scale": 2},
    "wallapop_phone_request_uk":  {"display_name": "Wallapop Phone Request (UK)",  "page": "Page 2", "frame": "wallapop4_uk",  "scale": 2},
    "wallapop_phone_request_es":  {"display_name": "Wallapop Phone Request (ES)",  "page": "Page 2", "frame": "wallapop4_es",  "scale": 2},
    "wallapop_phone_request_it":  {"display_name": "Wallapop Phone Request (IT)",  "page": "Page 2", "frame": "wallapop4_it",  "scale": 2},
    "wallapop_phone_request_fr":  {"display_name": "Wallapop Phone Request (FR)",  "page": "Page 2", "frame": "wallapop4_fr",  "scale": 2},
    "wallapop_phone_request_pr":  {"display_name": "Wallapop Phone Request (PT)",  "page": "Page 2", "frame": "wallapop4_pr",  "scale": 2},
    "wallapop_email_payment_uk":  {"display_name": "Wallapop Email Payment (UK)",  "page": "Page 2", "frame": "wallapop5_uk",  "scale": 2},
    "wallapop_email_payment_es":  {"display_name": "Wallapop Email Payment (ES)",  "page": "Page 2", "frame": "wallapop5_es",  "scale": 2},
    "wallapop_email_payment_it":  {"display_name": "Wallapop Email Payment (IT)",  "page": "Page 2", "frame": "wallapop5_it",  "scale": 2},
    "wallapop_email_payment_fr":  {"display_name": "Wallapop Email Payment (FR)",  "page": "Page 2", "frame": "wallapop5_fr",  "scale": 2},
    "wallapop_email_payment_pr":  {"display_name": "Wallapop Email Payment (PT)",  "page": "Page 2", "frame": "wallapop5_pr",  "scale": 2},
    "wallapop_sms_payment_uk":    {"display_name": "Wallapop SMS Payment (UK)",    "page": "Page 2", "frame": "wallapop6_uk",  "scale": 2},
    "wallapop_sms_payment_es":    {"display_name": "Wallapop SMS Payment (ES)",    "page": "Page 2", "frame": "wallapop6_es",  "scale": 2},
    "wallapop_sms_payment_it":    {"display_name": "Wallapop SMS Payment (IT)",    "page": "Page 2", "frame": "wallapop6_it",  "scale": 2},
    "wallapop_sms_payment_fr":    {"display_name": "Wallapop SMS Payment (FR)",    "page": "Page 2", "frame": "wallapop6_fr",  "scale": 2},
    "wallapop_sms_payment_pr":    {"display_name": "Wallapop SMS Payment (PT)",    "page": "Page 2", "frame": "wallapop6_pr",  "scale": 2},
    "wallapop_qr_uk":             {"display_name": "Wallapop QR (UK)",             "page": "Page 2", "frame": "wallapop7_uk",  "scale": 2},
    "wallapop_qr_es":             {"display_name": "Wallapop QR (ES)",             "page": "Page 2", "frame": "wallapop7_es",  "scale": 2},
    "wallapop_qr_it":             {"display_name": "Wallapop QR (IT)",             "page": "Page 2", "frame": "wallapop7_it",  "scale": 2},
    "wallapop_qr_fr":             {"display_name": "Wallapop QR (FR)",             "page": "Page 2", "frame": "wallapop7_fr",  "scale": 2},
    "wallapop_qr_pr":             {"display_name": "Wallapop QR (PT)",             "page": "Page 2", "frame": "wallapop7_pr",  "scale": 2},

    # === 2DEHANDS / 2EMEMAIN ===
    "2dehands": {"display_name": "2dehands (NL)", "page": "Page 2", "frame": "2dehands1", "scale": 2},
    "2ememain": {"display_name": "2ememain (FR)", "page": "Page 2", "frame": "2ememain1", "scale": 2},

    # === KLEINANZEIGEN ===
    "kleize": {"display_name": "Kleinanzeigen", "page": "Page 2", "frame": "kleize1", "scale": 2},

    # === CONTO ===
    "conto_long":  {"display_name": "Conto Long",  "page": "Page 2", "frame": "conto1_long",  "scale": 2},
    "conto_short": {"display_name": "Conto Short", "page": "Page 2", "frame": "conto1_short", "scale": 2},

    # === DEPOP ===
    "depop_au":              {"display_name": "Depop QR (Australia)",        "page": "Page 2", "frame": "depop1_au", "scale": 2},
    "depop_au_email_request":{"display_name": "Depop Email Request (AU)",    "page": "Page 2", "frame": "depop2_au", "scale": 2},
    "depop_au_email_confirm":{"display_name": "Depop Email Confirm (AU)",    "page": "Page 2", "frame": "depop3_au", "scale": 2},
    "depop_au_sms_request":  {"display_name": "Depop SMS Request (AU)",      "page": "Page 2", "frame": "depop4_au", "scale": 2},
    "depop_au_sms_confirm":  {"display_name": "Depop SMS Confirm (AU)",      "page": "Page 2", "frame": "depop5_au", "scale": 2},
    "depop_uk":              {"display_name": "Depop (UK)",                  "page": "Page 2", "frame": "depop1_uk", "scale": 2},
    "depop_us":              {"display_name": "Depop (US)",                  "page": "Page 2", "frame": "depop1_us", "scale": 2},
    "depop_it":              {"display_name": "Depop (Italy)",               "page": "Page 2", "frame": "depop1_it", "scale": 2},
}


def get_all_services():
    return list(SERVICES_CONFIG.keys())


def get_service_config(service_name: str) -> dict:
    return SERVICES_CONFIG.get(service_name)


def get_services_by_group():
    return {
        "Markt": [
            "markt_qr_uk", "markt_qr_nl",
            "markt_email_request_uk", "markt_email_request_nl",
            "markt_phone_request_uk", "markt_phone_request_nl",
            "markt_email_payment_uk", "markt_email_payment_nl",
            "markt_sms_payment_uk",   "markt_sms_payment_nl",
        ],
        "Subito": [
            "subito_email_request_uk", "subito_email_request_nl",
            "subito_phone_request_uk", "subito_phone_request_nl",
            "subito_email_payment_uk", "subito_email_payment_nl",
            "subito_sms_payment_uk",   "subito_sms_payment_nl",
            "subito_qr_uk",            "subito_qr_nl",
        ],
        "Wallapop": [
            "wallapop_email_request_uk", "wallapop_email_request_es",
            "wallapop_email_request_it", "wallapop_email_request_fr",
            "wallapop_email_request_pr",
            "wallapop_phone_request_uk", "wallapop_phone_request_es",
            "wallapop_phone_request_it", "wallapop_phone_request_fr",
            "wallapop_phone_request_pr",
            "wallapop_email_payment_uk", "wallapop_email_payment_es",
            "wallapop_email_payment_it", "wallapop_email_payment_fr",
            "wallapop_email_payment_pr",
            "wallapop_sms_payment_uk",   "wallapop_sms_payment_es",
            "wallapop_sms_payment_it",   "wallapop_sms_payment_fr",
            "wallapop_sms_payment_pr",
            "wallapop_qr_uk", "wallapop_qr_es",
            "wallapop_qr_it", "wallapop_qr_fr", "wallapop_qr_pr",
        ],
        "2dehands/2ememain": ["2dehands", "2ememain"],
        "Kleinanzeigen": ["kleize"],
        "Conto": ["conto_long", "conto_short"],
        "Depop": [
            "depop_au", "depop_au_email_request", "depop_au_email_confirm",
            "depop_au_sms_request", "depop_au_sms_confirm",
            "depop_uk", "depop_us", "depop_it",
        ],
    }
