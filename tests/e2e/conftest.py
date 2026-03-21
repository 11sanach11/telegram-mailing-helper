"""
E2E test fixtures.

Starts a real BottleServer with a real SQLite DB.  Outbound HTTP calls to the
Telegram Bot API (api.telegram.org) are intercepted at the transport level by
the `responses` library via TelegramApiMock — analogous to Spring's
MockRestServiceServer.  No real Telegram API calls are made; all calls are
recorded and can be asserted on in tests.

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


TEST_TOKEN = "1234567890:AAtest_token_for_e2e_testing"


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
    it.  Localhost calls pass through normally so the Bottle server is
    reachable by the test HTTP client.
    """
    mock = TelegramApiMock(token=TEST_TOKEN)
    mock.start()
    yield mock
    mock.stop()


# ---------------------------------------------------------------------------
# Main session fixture – starts the app server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_server(tmp_path_factory, tg_mock):
    """
    Starts the Bottle web server with a temporary SQLite DB.
    Returns a dict with base_url, dao, bot_name, token, tg_mock.

    The tg_mock fixture is injected here to guarantee HTTP interception is
    active before any application code (including Bot.__init__) runs.
    """
    tmp = tmp_path_factory.mktemp("e2e")
    db_file = str(tmp / "e2e.db")
    data_dir = str(tmp / "data")
    data_dir_path = Path(data_dir)
    data_dir_path.mkdir(parents=True, exist_ok=True)

    port = _free_port()
    base_url = f"http://localhost:{port}"

    config_data = {
        "db": {"dbFile": db_file},
        "server": {"port": port, "host": "localhost", "engine": "wsgiref"},
        "rootConfigDir": str(data_dir_path) + "/",
        "telegramToken": TEST_TOKEN,
        "telegramTokens": {},
        "telegramWebhookURL": base_url,
        "logFileName": str(tmp / "app.log"),
        "logOnlyInFile": False,
    }
    config_file = str(tmp / "config.json")
    Path(config_file).write_text(json.dumps(config_data))

    old_argv = sys.argv[:]
    sys.argv = [sys.argv[0], config_file]

    # No telegram.Bot patching needed — the real Bot object is used and its
    # outbound HTTP calls are intercepted by tg_mock (responses library).
    from telegram_mailing_help.appConfig import prepareAndGetConfigOnly
    from telegram_mailing_help.db.migration import Migration
    from telegram_mailing_help.db.dao import Dao
    from telegram_mailing_help.logic.listPreparation import Preparation
    from telegram_mailing_help.telegram.bot import MailingBot
    from telegram_mailing_help.web.server import BottleServer
    from telegram_mailing_help.telegramMailingHelper import _SINGLE_MODE_CONST

    app_config = prepareAndGetConfigOnly()

    Migration(app_config, None).migrate()

    dao = Dao(app_config, None)
    preparation = Preparation(app_config, dao)

    mailing_bot = MailingBot(
        botName=_SINGLE_MODE_CONST,
        telegramToken=TEST_TOKEN,
        webHookMode=True,
        telegramWebhookURL=base_url,
        db=dao,
        preparation=preparation,
    )
    mailing_bot.start()  # calls setWebhook → intercepted by tg_mock

    server = BottleServer(
        config=app_config,
        daoMap={_SINGLE_MODE_CONST: dao},
        preparationMapParam={_SINGLE_MODE_CONST: preparation},
        tbotMap={_SINGLE_MODE_CONST: mailing_bot},
    )
    server.start()

    sys.argv = old_argv

    assert _wait_server(f"{base_url}/info"), f"App server did not start at {base_url}"

    yield {
        "base_url": base_url,
        "dao": dao,
        "preparation": preparation,
        "bot": mailing_bot,
        "bot_name": _SINGLE_MODE_CONST,
        "token": TEST_TOKEN,
        "tg_mock": tg_mock,
    }

    mailing_bot.stop()  # calls deleteWebhook → intercepted by tg_mock


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

# In Bottle 0.12.25, auth_basic checks `user is None` before calling the
# check function, so requests without any Authorization header always get 401
# even in single-bot mode. We pass dummy credentials so the header is present;
# is_auth_user returns True for any creds in single-bot mode.
_HTTP_CREDENTIALS = {"username": "admin", "password": "admin"}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, base_url):
    return {
        **browser_context_args,
        "base_url": base_url,
        "http_credentials": _HTTP_CREDENTIALS,
    }
