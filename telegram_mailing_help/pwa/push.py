import json
import logging
import secrets
from typing import Optional

log = logging.getLogger("pwa.push")


def _generate_vapid_keys():
    """Generate VAPID key pair. Returns (private_key_pem_str, public_key_base64url_str)."""
    from py_vapid import Vapid01
    import base64
    vapid = Vapid01()
    vapid.generate_keys()
    private_pem = vapid.private_pem().decode('utf-8')
    # Public key as URL-safe base64 (uncompressed point, 65 bytes)
    pub_bytes = vapid.public_key.public_bytes(
        encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.X962,
        format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PublicFormat']).PublicFormat.UncompressedPoint
    )
    public_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode('utf-8')
    return private_pem, public_b64


def get_or_create_vapid_keys(dao):
    """Return (private_key_pem, public_key_base64url), auto-generating if needed."""
    private = dao.getValueFromStorage("vapid_private_key")
    public = dao.getValueFromStorage("vapid_public_key")
    if not private or not public:
        private, public = _generate_vapid_keys()
        dao.setValueInfoStorage("vapid_private_key", private)
        dao.setValueInfoStorage("vapid_public_key", public)
    return private, public


def send_push_notification(sub, title: str, body: str, vapid_private_key: str, vapid_claims: dict) -> bool:
    """Send a push notification to a single PushSubscription. Returns True on success."""
    from pywebpush import webpush, WebPushException
    sub_info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }
    data = json.dumps({"title": title, "body": body})
    try:
        webpush(
            subscription_info=sub_info,
            data=data,
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
        return True
    except WebPushException as ex:
        log.warning("Push failed for endpoint %s: %s", sub.endpoint, ex)
        return False
    except Exception as ex:
        log.warning("Unexpected push error for endpoint %s: %s", sub.endpoint, ex)
        return False


class PushBroadcaster:
    """Sends PWA push notifications for admin-level events (new user, low blocks)."""

    def __init__(self, dao, vapid_subject: str):
        self._dao = dao
        self._vapid_subject = vapid_subject

    def _get_claims(self):
        return {"sub": self._vapid_subject}

    def _get_private_key(self):
        return self._dao.getValueFromStorage("vapid_private_key")

    def _send_to_admin_subs(self, title: str, body: str):
        """Find subscriptions for the configured admin Telegram IDs and push to them."""
        private_key = self._get_private_key()
        if not private_key:
            return
        claims = self._get_claims()
        admin_ids = set()
        for storage_key in ("send_notification_about_new_user_to_telegram_id",
                            "send_notification_only_5_blocks_left_to_telegram_id"):
            val = self._dao.getValueFromStorage(storage_key)
            if val:
                admin_ids.add(val.strip())

        for telegram_id in admin_ids:
            user = self._dao.getUserByTelegramId(telegram_id)
            if user:
                for sub in self._dao.getPushSubscriptionsByUserId(user.id):
                    send_push_notification(sub, title, body, private_key, claims)

    def notify_new_user(self, user):
        try:
            self._send_to_admin_subs(
                "Новый пользователь",
                f"{user.name} зарегистрировался в приложении"
            )
        except Exception as e:
            log.warning("notify_new_user push failed: %s", e)

    def notify_low_blocks(self, group_name: str, count: int):
        try:
            self._send_to_admin_subs(
                "Мало блоков",
                f"В списке «{group_name}» осталось {count} свободных блоков"
            )
        except Exception as e:
            log.warning("notify_low_blocks push failed: %s", e)
