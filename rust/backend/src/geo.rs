use serde_json::Value;

/// Copy of Python GEO_CONFIG from app/api.py (1:1 as JSON).
///
/// Keeping it as JSON ensures the response structure stays identical.
pub fn geo_config() -> Value {
    serde_json::json!({
      "nl": {
        "name": "Netherlands",
        "services": {
          "markt": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]},
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "phone_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]}
            }
          },
          "subito": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "phone_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]}
            }
          },
          "2dehands": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]}
            }
          }
        }
      },
      "be": {
        "name": "Belgium",
        "services": {
          "2ememain": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]}
            }
          }
        }
      },
      "it": {
        "name": "Italy",
        "services": {
          "subito": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "name", "address"]},
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "name", "address"]},
              "email_confirm": {"endpoint": "/generate", "fields": ["title", "price", "photo", "name", "address"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "name", "address"]},
              "sms_confirm": {"endpoint": "/generate", "fields": ["title", "price", "photo", "name", "address"]}
            }
          },
          "conto": {
            "methods": {
              "payment": {"endpoint": "/generate", "fields": ["title", "price"]}
            }
          },
          "wallapop": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]}
            }
          }
        }
      },
      "de": {
        "name": "Germany",
        "services": {
          "kleinanzeigen": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]}
            }
          }
        }
      },
      "es": {
        "name": "Spain",
        "services": {
          "wallapop": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]}
            }
          }
        }
      },
      "uk": {
        "name": "United Kingdom",
        "services": {
          "markt": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]},
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "phone_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]}
            }
          },
          "subito": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "phone_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo"]}
            }
          },
          "wallapop": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]}
            }
          }
        }
      },
      "fr": {
        "name": "France",
        "services": {
          "wallapop": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]}
            }
          }
        }
      },
      "pr": {
        "name": "Portugal",
        "services": {
          "wallapop": {
            "methods": {
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "email_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "sms_payment": {"endpoint": "/generate", "fields": ["title", "price", "photo", "seller_name", "seller_photo"]},
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]}
            }
          }
        }
      },
      "au": {
        "name": "Australia",
        "services": {
          "depop": {
            "methods": {
              "qr": {"endpoint": "/generate", "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]},
              "email_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "email_confirm": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_request": {"endpoint": "/generate", "fields": ["title", "price", "photo"]},
              "sms_confirm": {"endpoint": "/generate", "fields": ["title", "price", "photo"]}
            }
          }
        }
      }
    })
}
