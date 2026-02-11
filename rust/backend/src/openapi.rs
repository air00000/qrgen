use axum::Router;
use serde_json::{json, Value};
use utoipa::{Modify, OpenApi};
use utoipa_swagger_ui::SwaggerUi;

/// GEO_CONFIG mirrors `app/api.py` and is used by GET /services and request validation.
///
/// Kept as JSON for flexibility while the Rust implementation is still a skeleton.
pub static GEO_CONFIG: once_cell::sync::Lazy<Value> = once_cell::sync::Lazy::new(|| {
    json!({
      "nl": {
        "name": "Netherlands",
        "services": {
          "markt": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo"]},
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "phone_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo"]}
          }},
          "2dehands": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo"]}
          }}
        }
      },
      "be": {
        "name": "Belgium",
        "services": {
          "2ememain": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo"]}
          }}
        }
      },
      "it": {
        "name": "Italy",
        "services": {
          "subito": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","name","address"]},
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","name","address"]},
            "email_confirm": {"endpoint": "/generate", "fields": ["title","price","photo","name","address"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","name","address"]},
            "sms_confirm": {"endpoint": "/generate", "fields": ["title","price","photo","name","address"]}
          }},
          "conto": {"methods": {
            "payment": {"endpoint": "/generate", "fields": ["title","price"]}
          }},
          "wallapop": {"methods": {
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]}
          }}
        }
      },
      "de": {
        "name": "Germany",
        "services": {
          "kleinanzeigen": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo"]}
          }}
        }
      },
      "es": {
        "name": "Spain",
        "services": {
          "wallapop": {"methods": {
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]}
          }}
        }
      },
      "uk": {
        "name": "United Kingdom",
        "services": {
          "markt": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo"]},
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "phone_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo"]}
          }},
          "wallapop": {"methods": {
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]}
          }}
        }
      },
      "fr": {
        "name": "France",
        "services": {
          "wallapop": {"methods": {
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]}
          }}
        }
      },
      "pr": {
        "name": "Portugal",
        "services": {
          "wallapop": {"methods": {
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "email_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "sms_payment": {"endpoint": "/generate", "fields": ["title","price","photo","seller_name","seller_photo"]},
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]}
          }}
        }
      },
      "au": {
        "name": "Australia",
        "services": {
          "depop": {"methods": {
            "qr": {"endpoint": "/generate", "fields": ["title","price","url","photo","seller_name","seller_photo"]},
            "email_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "email_confirm": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "sms_request": {"endpoint": "/generate", "fields": ["title","price","photo"]},
            "sms_confirm": {"endpoint": "/generate", "fields": ["title","price","photo"]}
          }}
        }
      }
    })
});

#[derive(OpenApi)]
#[openapi(
    paths(
        crate::routes::health,
        crate::routes::services,
        crate::routes::generate,
    ),
    components(
        schemas(crate::routes::UniversalRequest)
    ),
    modifiers(&SecurityAddon),
    tags(
        (name = "qrgen", description = "QR Generator Rust backend skeleton")
    )
)]
pub struct ApiDoc;

struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        use utoipa::openapi::security::{ApiKey, ApiKeyValue, SecurityScheme};
        openapi.components = openapi.components.take().map(|mut c| {
            c.add_security_scheme(
                "api_key",
                SecurityScheme::ApiKey(ApiKey::Header(ApiKeyValue::new("X-API-Key"))),
            );
            c
        });
    }
}

pub fn router() -> Router<crate::state::AppState> {
    Router::new()
        .route(
            "/openapi.json",
            axum::routing::get(|| async move { axum::Json(ApiDoc::openapi()) }),
        )
        .merge(
            SwaggerUi::new("/docs")
                .url("/openapi.json", ApiDoc::openapi()),
        )
}
