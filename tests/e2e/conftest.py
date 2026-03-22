"""
E2E test fixtures.

Starts the application through TelegramMailingHelper — the same entry point
used in production.  Outbound HTTP calls to the Telegram Bot API
(api.telegram.org) are intercepted at the transport level by the `responses`
library via TelegramApiMock — analogous to Spring's MockRestServiceServer.
No real Telegram API calls are made; all calls are recorded and can be
asserted on in tests.

Playwright is used for browser and HTTP-level tests.
"""
import json
import socket
import sys
import time
from pathlib import Path

import pytest
import requests as _http

from tests.e2e.tg_mock import TelegramApiMock


TEST_TOKEN    = "1234567890:AAtest_token_for_e2e_testing"
# In multi-bot mode (telegramTokens) TelegramMailingHelper starts the bot in
# webhook mode.  We use a single-entry telegramTokens dict instead of the
# legacy telegramToken field so that webHookMode=True is derived automatically.
_BOT_NAME_SINGLE = "single_bot"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _wait_server(url: str, timeout: float = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = _http.get(url, timeout=1)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def wait_for(fn, timeout: float = 5, interval: float = 0.1) -> bool:
    """Poll fn() until it returns truthy or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Session-scoped Telegram API mock — started before the app server so that
# even the initial setWebhook call is intercepted.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tg_mock() -> TelegramApiMock:
    """
    HTTP-level Telegram Bot API mock, active for the whole test session.

    Intercepts every outbound `requests` call to api.telegram.org and records
    it.  Localhost calls pass through normally so the server is reachable.
    """
    mock = TelegramApiMock(token=TEST_TOKEN)
    mock.start()
    yield mock
    mock.stop()


# ---------------------------------------------------------------------------
# Main session fixture – starts the app server via TelegramMailingHelper
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_server(tmp_path_factory, tg_mock):
    """
    Starts the application using TelegramMailingHelper (single-bot mode) with
    a temporary SQLite DB.  Returns a dict with base_url, dao, bot, helper,
    and other components for use in tests.

    sys.argv is kept pointing at the config file for the duration of the
    session so that signal-handler reload tests can call
    prepareAndGetConfigOnly() and read the live config.

    The tg_mock fixture is injected here to guarantee HTTP interception is
    active before any application code (including Bot.__init__) runs.
    """
    tmp      = tmp_path_factory.mktemp("e2e")
    db_file  = str(tmp / "e2e.db")
    data_dir = str(tmp / "data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    port     = _free_port()
    base_url = f"http://localhost:{port}"

    config_data = {
        "db":       {"dbFile": db_file},
        "server":   {"port": port, "host": "localhost", "engine": "wsgiref"},
        "rootConfigDir": data_dir + "/",
        # telegramToken=None forces multi-bot mode, which makes TelegramMailingHelper
        # start the bot in webhook mode (webHookMode = telegramToken is None).
        "telegramToken":  None,
        "telegramTokens": {
            _BOT_NAME_SINGLE: {
                "token":  TEST_TOKEN,
                "logins": [{"user": "admin", "password": "admin"}],
            },
        },
        "telegramWebhookURL": base_url,
        "logFileName":   str(tmp / "app.log"),
        "logOnlyInFile": False,
    }
    config_file = str(tmp / "config.json")
    Path(config_file).write_text(json.dumps(config_data))

    old_argv  = sys.argv[:]
    sys.argv  = [sys.argv[0], config_file]

    from telegram_mailing_help.appConfig import prepareAndGetConfigOnly
    from telegram_mailing_help.telegramMailingHelper import TelegramMailingHelper

    app_config = prepareAndGetConfigOnly()
    helper     = TelegramMailingHelper(app_config)

    assert _wait_server(f"{base_url}/info"), f"App server did not start at {base_url}"

    yield {
        "base_url":    base_url,
        "config_file": config_file,
        "dao":         helper.daoList[_BOT_NAME_SINGLE],
        "preparation": helper.preparationList[_BOT_NAME_SINGLE],
        "bot":         helper.telegramBotList[_BOT_NAME_SINGLE],
        "bot_name":    _BOT_NAME_SINGLE,
        "token":       TEST_TOKEN,
        "tg_mock":     tg_mock,
        "helper":      helper,
    }

    for bot in list(helper.telegramBotList.values()):
        bot.stop()

    sys.argv = old_argv


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url(app_server):
    return app_server["base_url"]


@pytest.fixture(scope="session")
def dao(app_server):
    return app_server["dao"]


@pytest.fixture(scope="session")
def tg_token(app_server):
    return app_server["token"]


@pytest.fixture(scope="session")
def bot_name(app_server):
    return app_server["bot_name"]


# ---------------------------------------------------------------------------
# pytest-playwright integration
# Override browser_context_args to inject our base_url.
# Headed / headless is controlled via pytest-playwright's --headed flag.
# ---------------------------------------------------------------------------

# In single-bot mode is_auth_user returns True for any credentials, so we
# just pass dummy ones to satisfy FastAPI's HTTPBasic header requirement.
_HTTP_CREDENTIALS = {"username": "admin", "password": "admin"}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, base_url):
    return {
        **browser_context_args,
        "base_url": base_url,
        "http_credentials": _HTTP_CREDENTIALS,
    }
