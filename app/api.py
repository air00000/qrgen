# app/api.py
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Extra
from typing import Optional, Any, List

from app.services.pdf import (
    create_image_marktplaats, create_image_subito, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError
)
from app.services.subito_variants import (
    create_image_subito_email_request, create_image_subito_email_confirm,
    create_image_subito_sms_request, create_image_subito_sms_confirm
)
# create_wallapop_phone_request,
from app.services.wallapop_variants import (
    create_wallapop_email_request,
    create_wallapop_sms_request,
    create_wallapop_email_payment,
    create_wallapop_sms_payment,
    create_wallapop_qr,
)
from app.services.twodehands import create_2dehands_image, DehandsGenerationError
from app.services.kleize import create_kleize_image, KleizeGenerationError
from app.services.conto import create_conto_image, ContoGenerationError
from app.services.depop import create_depop_image, DepopGenerationError
from app.services.depop_variants import (
    create_depop_email_request, create_depop_email_confirm,
    create_depop_sms_request, create_depop_sms_confirm,
    DepopVariantError
)
from app.services.apikey import validate_key, get_key_name
from app.utils.notifications import send_api_notification_sync

app = FastAPI(title="QR Generator API")


# ======== Конфигурация GEO с полями ========
GEO_CONFIG = {
    "nl": {
        "name": "Netherlands",
        "services": {
            "marktplaats": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo"]
                    }
                }
            },
            "2dehands": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo"]
                    }
                }
            }
        }
    },
    "be": {
        "name": "Belgium",
        "services": {
            "2ememain": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo"]
                    }
                }
            }
        }
    },
    "it": {
        "name": "Italy",
        "services": {
            "subito": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "name", "address"]
                    },
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "name", "address"]
                    },
                    "email_confirm": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "name", "address"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "name", "address"]
                    },
                    "sms_confirm": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "name", "address"]
                    }
                }
            },
            "conto": {
                "methods": {
                    "payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price"]
                    }
                }
            },
            "wallapop": {
                "methods": {
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "email_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    }
                }
            }
        }
    },
    "de": {
        "name": "Germany",
        "services": {
            "kleinanzeigen": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo"]
                    }
                }
            }
        }
    },
    "es": {
        "name": "Spain",
        "services": {
            "wallapop": {
                "methods": {
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "email_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    }
                }
            }
        }
    },
    "uk": {
        "name": "United Kingdom",
        "services": {
            "wallapop": {
                "methods": {
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "email_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    }
                }
            }
        }
    },
    "fr": {
        "name": "France",
        "services": {
            "wallapop": {
                "methods": {
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "email_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    }
                }
            }
        }
    },
    "pr": {
        "name": "Portugal",
        "services": {
            "wallapop": {
                "methods": {
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "email_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "sms_payment": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo", "seller_name", "seller_photo"]
                    },
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    }
                }
            }
        }
    },
    "au": {
        "name": "Australia",
        "services": {
            "depop": {
                "methods": {
                    "qr": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "url", "photo", "seller_name", "seller_photo"]
                    },
                    "email_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo"]
                    },
                    "email_confirm": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo"]
                    },
                    "sms_request": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo"]
                    },
                    "sms_confirm": {
                        "endpoint": "/generate",
                        "fields": ["title", "price", "photo"]
                    }
                }
            }
        }
    }
}


# ======== Зависимость для проверки API ключа ========
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Please provide X-API-Key header"
        )

    if not validate_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return get_key_name(x_api_key)


# ======== Универсальная модель запроса ========
class UniversalRequest(BaseModel):
    """
    Универсальная модель - принимает любые поля.
    Отправляй все поля сразу, API возьмёт только нужные.
    """
    country: str
    service: str
    method: str
    
    # Все возможные поля - отправляй всё, API возьмёт нужное
    title: Optional[str] = None
    price: Optional[float] = None
    url: Optional[str] = None
    photo: Optional[str] = None          # base64 - фото товара
    name: Optional[str] = None           # для Subito - имя покупателя
    address: Optional[str] = None        # для Subito - адрес
    seller_name: Optional[str] = None    # для Wallapop/Depop - имя продавца
    seller_photo: Optional[str] = None   # base64 - фото/аватар продавца (для Wallapop и Depop)
    
    class Config:
        extra = Extra.ignore  # Игнорируем лишние поля


# ===== Field validation removed =====
# Per requirements: missing data should not raise errors
# Treat missing fields as empty values ("" / None / empty object)
# Only return errors for truly invalid request structure or unrecoverable internal failures


# ======== GET /get-geo ========
@app.get("/get-geo")
async def get_geo(key_name: str = Depends(verify_api_key)):
    """
    Получить список доступных стран, сервисов, методов и полей.
    
    Возвращает структуру с полями которые используются для каждого метода.
    Отправляй запрос со всеми полями - API возьмёт только нужные.
    
    Пример ответа:
    {
        "nl": {
            "name": "Netherlands",
            "services": {
                "marktplaats": {
                    "methods": {
                        "qr": {
                            "endpoint": "/generate",
                            "fields": ["title", "price", "url", "photo"]
                        }
                    }
                }
            }
        }
    }
    """
    return GEO_CONFIG


# ======== POST /generate ========
@app.post("/generate")
async def generate(
    req: UniversalRequest,
    key_name: str = Depends(verify_api_key)
):
    """
    Универсальный эндпоинт генерации.
    
    Отправляй все поля сразу - API возьмёт только нужные для выбранного country/service/method.
    Если каких-то данных не хватает - вернётся ошибка с указанием чего не хватает.
    
    Пример запроса:
    {
        "country": "nl",
        "service": "marktplaats",
        "method": "qr",
        "title": "iPhone 15",
        "price": 999.99,
        "url": "https://example.com",
        "photo": "base64...",
        "seller_name": "будет проигнорировано для marktplaats",
        "name": "тоже будет проигнорировано"
    }
    """
    country = req.country.lower()
    service = req.service.lower()
    method = req.method.lower()
    
    # Собираем все данные в dict
    data = {
        "title": req.title,
        "price": req.price,
        "url": req.url,
        "photo": req.photo,
        "name": req.name,
        "address": req.address,
        "seller_name": req.seller_name,
        "seller_photo": req.seller_photo,
    }
    
    # Валидация country
    if country not in GEO_CONFIG:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown country: {country}. Available: {list(GEO_CONFIG.keys())}"
        )
    
    # Валидация service
    if service not in GEO_CONFIG[country]["services"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown service '{service}' for country '{country}'. "
                   f"Available: {list(GEO_CONFIG[country]['services'].keys())}"
        )
    
    # Валидация method
    service_methods = GEO_CONFIG[country]["services"][service]["methods"]
    if method not in service_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown method '{method}' for service '{service}'. "
                   f"Available: {list(service_methods.keys())}"
        )
    
    # Роутинг и генерация
    try:
        image_data = _route_generation(country, service, method, data)
        
        service_name = f"{service}_{method}" if method not in ("qr", "payment") else service
        send_api_notification_sync(
            service=service_name, 
            key_name=key_name, 
            title=data.get("title") or "Unknown", 
            success=True
        )
        return Response(content=image_data, media_type="image/png")
        
    except (PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError, 
            DehandsGenerationError, KleizeGenerationError, ContoGenerationError,
            DepopGenerationError, DepopVariantError) as e:
        # Ошибка генерации (технические проблемы)
        send_api_notification_sync(
            service=f"{service}_{method}", 
            key_name=key_name, 
            title=data.get("title") or "Unknown", 
            success=False, 
            error=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Неизвестная ошибка
        send_api_notification_sync(
            service=f"{service}_{method}", 
            key_name=key_name, 
            title=data.get("title") or "Unknown", 
            success=False, 
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


def _route_generation(country: str, service: str, method: str, data: dict) -> bytes:
    """Роутинг генерации без проверки данных - missing fields treated as empty"""
    
    from app.utils.helpers import get_field_with_default
    
    context = f"{country}/{service}/{method}"
    
    # Helper to safely get fields with defaults
    def get(field, default=""):
        return get_field_with_default(data, field, default)
    
    # === NETHERLANDS ===
    if country == "nl":
        if service == "marktplaats":
            return create_image_marktplaats(
                get("title"), get("price", 0.0), get("photo"), get("url")
            )
        
        elif service == "2dehands":
            return create_2dehands_image(
                get("title"), get("price", 0.0), get("photo"), get("url"), "nl"
            )
    
    # === BELGIUM ===
    elif country == "be":
        if service == "2ememain":
            return create_2dehands_image(
                get("title"), get("price", 0.0), get("photo"), get("url"), "fr"
            )
    
    # === ITALY ===
    elif country == "it":
        if service == "subito":
            if method == "qr":
                return create_image_subito(
                    get("title"), get("price", 0.0), get("photo"), get("url"),
                    get("name"), get("address")
                )
            elif method == "email_request":
                return create_image_subito_email_request(
                    get("title"), get("price", 0.0), get("photo"),
                    get("name"), get("address")
                )
            elif method == "email_confirm":
                return create_image_subito_email_confirm(
                    get("title"), get("price", 0.0), get("photo"),
                    get("name"), get("address")
                )
            elif method == "sms_request":
                return create_image_subito_sms_request(
                    get("title"), get("price", 0.0), get("photo"),
                    get("name"), get("address")
                )
            elif method == "sms_confirm":
                return create_image_subito_sms_confirm(
                    get("title"), get("price", 0.0), get("photo"),
                    get("name"), get("address")
                )
        
        elif service == "conto":
            return create_conto_image(get("title"), get("price", 0.0))
        
        elif service == "wallapop":
            lang = "it"
            
            if method == "email_request":
                return create_wallapop_email_request(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "sms_request":
                return create_wallapop_sms_request(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "email_payment":
                return create_wallapop_email_payment(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "sms_payment":
                return create_wallapop_sms_payment(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "qr":
                return create_wallapop_qr(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo"), get("url")
                )
    
    # === GERMANY ===
    elif country == "de":
        if service == "kleinanzeigen":
            return create_kleize_image(
                get("title"), get("price", 0.0), get("photo"), get("url")
            )
    
    # === SPAIN / UK / FRANCE / PORTUGAL (Wallapop) ===
    elif country in ("es", "uk", "fr", "pr"):
        if service == "wallapop":
            lang = country
            
            if method == "email_request":
                return create_wallapop_email_request(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "sms_request":
                return create_wallapop_sms_request(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "email_payment":
                return create_wallapop_email_payment(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "sms_payment":
                return create_wallapop_sms_payment(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo")
                )
            elif method == "qr":
                return create_wallapop_qr(
                    lang, get("title"), get("price", 0.0),
                    get("photo"), get("seller_name"), get("seller_photo"), get("url")
                )
    
    # === AUSTRALIA ===
    elif country == "au":
        if service == "depop":
            if method == "qr":
                return create_depop_image(
                    get("title"), get("price", 0.0), get("seller_name"),
                    get("photo"), get("seller_photo"), get("url")
                )
            elif method == "email_request":
                return create_depop_email_request(
                    get("title"), get("price", 0.0), get("photo")
                )
            elif method == "email_confirm":
                return create_depop_email_confirm(
                    get("title"), get("price", 0.0), get("photo")
                )
            elif method == "sms_request":
                return create_depop_sms_request(
                    get("title"), get("price", 0.0), get("photo")
                )
            elif method == "sms_confirm":
                return create_depop_sms_confirm(
                    get("title"), get("price", 0.0), get("photo")
                )
    
    raise PDFGenerationError(f"Unsupported combination: {context}")


# ======== Status ========
@app.get("/api/status")
async def api_status(key_name: str = Depends(verify_api_key)):
    """Проверка статуса API"""
    return {
        "status": "active",
        "key_name": key_name,
        "message": "API key is valid"
    }
