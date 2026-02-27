from telegram.ext import ContextTypes

from app.config import CFG
from app.services.subscriptions import has_active_subscription


def _extract_user_id(update_or_message) -> int | None:
    user = getattr(update_or_message, "effective_user", None)
    if not user:
        user = getattr(update_or_message, "from_user", None)
    return user.id if user else None


def has_generation_subscription(update_or_message) -> bool:
    uid = _extract_user_id(update_or_message)
    if uid is None:
        return False
    if uid in CFG.ADMIN_IDS:
        return True
    return has_active_subscription(uid)


def should_apply_watermark(update_or_message) -> bool:
    """Watermark policy:
    - no subscription/admin => watermark ON
    - active subscription/admin => watermark OFF
    """
    return not has_generation_subscription(update_or_message)


async def ensure_generation_access(update_or_message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Generations are available to everyone.

    Access is no longer blocked by subscription status.
    Subscription only controls watermark visibility.
    """
    return True
