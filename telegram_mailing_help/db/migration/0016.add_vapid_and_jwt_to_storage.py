from yoyo import step

steps = [
    step(
        "INSERT OR IGNORE INTO STORAGE (key, value, description) VALUES "
        "('vapid_private_key', '', 'VAPID private key for web push (auto-generated on first PWA startup)');"
    ),
    step(
        "INSERT OR IGNORE INTO STORAGE (key, value, description) VALUES "
        "('vapid_public_key', '', 'VAPID public key for web push (sent to frontend for push subscription)');"
    ),
    step(
        "INSERT OR IGNORE INTO STORAGE (key, value, description) VALUES "
        "('pwa_jwt_secret', '', 'JWT signing secret for PWA auth (auto-generated on first PWA startup)');"
    ),
]
