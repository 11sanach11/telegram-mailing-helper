"""
E2E Telegram webhook simulation tests.

Posts raw Telegram Update JSON to the /t_webhook/<bot_name>/<token> endpoint
and verifies side-effects in the database (user creation, etc.).

The Telegram Bot is mocked, so no real API calls go out.
Handlers run in the Dispatcher thread, so we poll the DB for side-effects.
"""
import time

import pytest
import requests

from tests.e2e.conftest import wait_for


# ---------------------------------------------------------------------------
# Helpers for building Telegram Update payloads
# ---------------------------------------------------------------------------

_UPDATE_COUNTER = iter(range(1, 100_000))


def _next_id() -> int:
    return next(_UPDATE_COUNTER)


def make_message_update(chat_id: int, text: str) -> dict:
    uid = _next_id()
    entities = []
    if text.startswith("/"):
        cmd = text.split()[0]
        entities = [{"offset": 0, "length": len(cmd), "type": "bot_command"}]
    return {
        "update_id": uid,
        "message": {
            "message_id": uid,
            "from": {
                "id": chat_id,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": f"testuser{chat_id}",
            },
            "chat": {
                "id": chat_id,
                "first_name": "Test",
                "last_name": "User",
                "username": f"testuser{chat_id}",
                "type": "private",
            },
            "date": int(time.time()),
            "text": text,
            "entities": entities,
        },
    }


def make_callback_query_update(chat_id: int, callback_data: str) -> dict:
    uid = _next_id()
    return {
        "update_id": uid,
        "callback_query": {
            "id": str(uid),
            "from": {
                "id": chat_id,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": f"testuser{chat_id}",
            },
            "message": {
                "message_id": uid,
                "from": {"id": 1234567890, "is_bot": True, "first_name": "Bot"},
                "chat": {
                    "id": chat_id,
                    "first_name": "Test",
                    "type": "private",
                },
                "date": int(time.time()),
                "text": "some bot message",
            },
            "chat_instance": "abc123",
            "data": callback_data,
        },
    }


def post_webhook(base_url: str, bot_name: str, token: str, payload: dict):
    url = f"{base_url}/t_webhook/{bot_name}/{token}"
    return requests.post(url, json=payload, timeout=5)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_wrong_token_rejected(base_url, bot_name):
    """Webhook with incorrect token must be rejected with an error status."""
    payload = make_message_update(chat_id=11111, text="/start")
    resp = post_webhook(base_url, bot_name, "0:wrong_token", payload)
    assert resp.status_code in (400, 500)


def test_new_user_registered_on_start(base_url, bot_name, tg_token, dao):
    """
    Posting a /start update from an unknown user must create the user in DB
    with state='new'.
    """
    chat_id = 20000001
    payload = make_message_update(chat_id=chat_id, text="/start")
    resp = post_webhook(base_url, bot_name, tg_token, payload)
    assert resp.status_code == 200

    # Dispatcher processes the update asynchronously – poll for DB change
    found = wait_for(
        lambda: dao.getUserByTelegramId(str(chat_id)) is not None,
        timeout=5,
    )
    assert found, "New user was not saved to DB after /start"

    user = dao.getUserByTelegramId(str(chat_id))
    assert user.state == "new"
    assert str(chat_id) in user.telegram_id


def test_known_unconfirmed_user_start_does_not_crash(base_url, bot_name, tg_token, dao):
    """
    Second /start from the same unconfirmed user must not create a duplicate
    and must return 200.
    """
    chat_id = 20000001  # same as previous test – user already in DB
    payload = make_message_update(chat_id=chat_id, text="/start")
    resp = post_webhook(base_url, bot_name, tg_token, payload)
    assert resp.status_code == 200

    all_users = [u for u in dao.getAllUsers() if u.telegram_id == str(chat_id)]
    assert len(all_users) == 1, "Duplicate user records created"


def test_info_command_processed(base_url, bot_name, tg_token):
    """/info command from any user must return 200 (handler runs without crash)."""
    chat_id = 20000002
    payload = make_message_update(chat_id=chat_id, text="/info")
    resp = post_webhook(base_url, bot_name, tg_token, payload)
    assert resp.status_code == 200


def test_callback_query_get_dispatch_group_names(base_url, bot_name, tg_token, dao):
    """
    callback_data='get_dispatch_group_names' for a new (unconfirmed) user
    must return 200 (triggers commandMain internally).
    """
    from datetime import datetime
    from telegram_mailing_help.db.dao import User, UserState

    chat_id = 20000003
    # Make sure user exists (new state)
    if dao.getUserByTelegramId(str(chat_id)) is None:
        dao.saveUser(User(
            id=None,
            telegram_id=str(chat_id),
            name="Callback Test User",
            state=UserState.NEW.value,
            created=datetime.now().isoformat(),
        ))

    payload = make_callback_query_update(chat_id, "get_dispatch_group_names")
    resp = post_webhook(base_url, bot_name, tg_token, payload)
    assert resp.status_code == 200


def test_confirmed_user_gets_dispatch_groups(base_url, bot_name, tg_token, dao):
    """
    A confirmed user sending /start must see available dispatch groups.
    We verify by checking that the handler ran without error (200 response).
    Actual Telegram API call assertions are in test_tg_api_calls.py.
    """
    from datetime import datetime
    from telegram_mailing_help.db.dao import User, UserState

    chat_id = 20000004
    # Ensure a confirmed user exists
    existing = dao.getUserByTelegramId(str(chat_id))
    if existing is None:
        existing = dao.saveUser(User(
            id=None,
            telegram_id=str(chat_id),
            name="Confirmed User",
            state=UserState.CONFIRMED.value,
            created=datetime.now().isoformat(),
        ))
    else:
        existing.state = UserState.CONFIRMED.value
        dao.saveUser(existing)

    payload = make_message_update(chat_id=chat_id, text="/start")
    resp = post_webhook(base_url, bot_name, tg_token, payload)
    assert resp.status_code == 200
