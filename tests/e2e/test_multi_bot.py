"""
E2E tests for multi-bot mode.

Uses TelegramMailingHelper as the single entry point (mirroring production),
configured with two independent bots (bot_alpha and bot_beta) each backed by
its own SQLite DB.  Tests cover:

  - data isolation  — users/lists created via one bot are invisible to the other
  - auth routing    — HTTP Basic Auth resolves to the correct bot's DAO
  - webhook routing — Telegram updates reach the correct bot's handler
  - config parsing  — TelegramMailingHelper validates single vs multi-bot config
  - signal handlers — stop and SIGHUP-reload handlers behave correctly
"""
import json
import signal as _signal
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests as _http

from tests.e2e.conftest import _free_port, _wait_server, wait_for

# ── Constants ─────────────────────────────────────────────────────────────────

TOKEN_ALPHA    = "1111111111:AAtoken_for_bot_alpha_testing"
TOKEN_BETA     = "2222222222:BBtoken_for_bot_beta_testing"
BOT_NAME_ALPHA = "bot_alpha"
BOT_NAME_BETA  = "bot_beta"
CREDS_ALPHA    = ("admin_alpha", "pass_alpha")
CREDS_BETA     = ("admin_beta",  "pass_beta")

_UPDATE_COUNTER = iter(range(200_000, 300_000))


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _next_id() -> int:
    return next(_UPDATE_COUNTER)


def _make_start(chat_id: int) -> dict:
    uid = _next_id()
    return {
        "update_id": uid,
        "message": {
            "message_id": uid,
            "from": {
                "id": chat_id, "is_bot": False,
                "first_name": "Multi", "last_name": "Tester",
                "username": f"multitester{chat_id}",
            },
            "chat": {
                "id": chat_id, "type": "private",
                "first_name": "Multi", "last_name": "Tester",
                "username": f"multitester{chat_id}",
            },
            "date": int(time.time()),
            "text": "/start",
            "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
        },
    }


def _post_webhook(base_url: str, bot_name: str, token: str, payload: dict):
    return _http.post(f"{base_url}/t_webhook/{bot_name}/{token}",
                      json=payload, timeout=5)


def _api(base_url: str, creds: tuple):
    """Return a thin HTTP client that carries the given credentials."""
    class _Client:
        def get(self, path):
            return _http.get(f"{base_url}{path}", auth=creds, timeout=5)

        def post(self, path, body):
            return _http.post(f"{base_url}{path}", json=body, auth=creds, timeout=5)

        def post_form(self, path, form):
            return _http.post(f"{base_url}{path}", data=form, auth=creds, timeout=5)

    return _Client()


# ── Multi-bot server fixture (module scope) ───────────────────────────────────

def _write_multi_bot_config(config_file: str, base_url: str, port: int,
                             data_dir: str, db_alpha: str, db_beta: str):
    """Write a two-bot config to *config_file*."""
    cfg = {
        "db":       {"dbFile": db_alpha},          # "main" db entry (alpha)
        "server":   {"port": port, "host": "localhost", "engine": "wsgiref"},
        "rootConfigDir": data_dir + "/",
        "telegramToken":  None,                    # multi-bot mode
        "telegramTokens": {
            BOT_NAME_ALPHA: {
                "token":  TOKEN_ALPHA,
                "logins": [{"user": CREDS_ALPHA[0], "password": CREDS_ALPHA[1]}],
            },
            BOT_NAME_BETA: {
                "token":  TOKEN_BETA,
                "logins": [{"user": CREDS_BETA[0], "password": CREDS_BETA[1]}],
            },
        },
        "telegramWebhookURL": base_url,
        "logFileName":   str(Path(data_dir).parent / "multi.log"),
        "logOnlyInFile": False,
    }
    Path(config_file).write_text(json.dumps(cfg))


@pytest.fixture(scope="module")
def multi_bot_server(tmp_path_factory, tg_mock):
    """
    Spin up a FastAPI server in multi-bot mode (two bots, two DBs) via
    TelegramMailingHelper.  Module-level globals in server.py are saved
    before setup and restored after teardown so single-bot tests elsewhere
    in the same pytest session are unaffected.

    sys.argv is kept pointing at the config file for the whole module so
    that signal-handler reload tests can call prepareAndGetConfigOnly().
    """
    import telegram_mailing_help.web.server as _srv

    _saved = {
        "dbMap":          _srv.dbMap.copy(),
        "preparationMap": _srv.preparationMap.copy(),
        "botMap":         _srv.botMap.copy(),
        "_appConfig":     _srv._appConfig,
    }

    tmp      = tmp_path_factory.mktemp("e2e_multi")
    port     = _free_port()
    base_url = f"http://localhost:{port}"

    db_alpha   = str(tmp / "alpha.db")
    db_beta    = str(tmp / "beta.db")
    data_dir   = str(tmp / "data")
    config_file = str(tmp / "config.json")
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    _write_multi_bot_config(config_file, base_url, port, data_dir,
                             db_alpha, db_beta)

    old_argv  = sys.argv[:]
    sys.argv  = [sys.argv[0], config_file]

    from telegram_mailing_help.appConfig import prepareAndGetConfigOnly
    from telegram_mailing_help.db.config import Configuration as DbConfig
    from telegram_mailing_help.telegramMailingHelper import TelegramMailingHelper
    import copy

    app_config = prepareAndGetConfigOnly()

    # Give each bot its own DB by creating per-bot configs
    cfg_alpha    = copy.deepcopy(app_config)
    cfg_alpha.db = DbConfig(dbFile=db_alpha)
    cfg_beta     = copy.deepcopy(app_config)
    cfg_beta.db  = DbConfig(dbFile=db_beta)

    # Run migrations separately so each DB is initialised before TelegramMailingHelper
    # calls prepareBotForStart (which runs migrations again — idempotent).
    from telegram_mailing_help.db.migration import Migration
    Migration(cfg_alpha, BOT_NAME_ALPHA).migrate()
    Migration(cfg_beta,  BOT_NAME_BETA).migrate()

    # Patch appConfig so prepareBotForStart uses the right DB per bot
    original_pbfs = TelegramMailingHelper.prepareBotForStart

    def _patched_pbfs(self_h, acfg, bot_name):
        if bot_name == BOT_NAME_ALPHA:
            acfg = cfg_alpha
        elif bot_name == BOT_NAME_BETA:
            acfg = cfg_beta
        original_pbfs(self_h, acfg, bot_name)

    TelegramMailingHelper.prepareBotForStart = _patched_pbfs
    try:
        helper = TelegramMailingHelper(app_config)
    finally:
        TelegramMailingHelper.prepareBotForStart = original_pbfs

    assert _wait_server(f"{base_url}/info"), \
        f"Multi-bot server did not start on port {port}"

    yield {
        "base_url":    base_url,
        "config_file": config_file,
        "db_alpha":    db_alpha,
        "db_beta":     db_beta,
        "data_dir":    data_dir,
        "dao_alpha":   helper.daoList[BOT_NAME_ALPHA],
        "dao_beta":    helper.daoList[BOT_NAME_BETA],
        "bot_alpha":   helper.telegramBotList[BOT_NAME_ALPHA],
        "bot_beta":    helper.telegramBotList[BOT_NAME_BETA],
        "tg_mock":     tg_mock,
        "helper":      helper,
        "port":        port,
    }

    for bot in list(helper.telegramBotList.values()):
        try:
            bot.stop()
        except Exception:
            pass

    _srv.dbMap          = _saved["dbMap"]
    _srv.preparationMap = _saved["preparationMap"]
    _srv.botMap         = _saved["botMap"]
    _srv._appConfig     = _saved["_appConfig"]

    sys.argv = old_argv


# ── Isolated helper factory (function scope, for signal / config tests) ───────


@pytest.fixture()
def make_helper(tmp_path, tg_mock):
    """
    Function-scoped factory that creates a TelegramMailingHelper from an
    explicit config dict, then tears it down after the test.

    Saves and restores server.py module-level globals so that the
    module-scoped multi_bot_server fixture is unaffected.

    Usage::

        def test_something(make_helper):
            helper, config_file = make_helper({
                "telegramToken": "123:abc", "telegramTokens": {},
                ...
            })
    """
    import telegram_mailing_help.web.server as _srv
    from telegram_mailing_help.appConfig import prepareAndGetConfigOnly
    from telegram_mailing_help.telegramMailingHelper import TelegramMailingHelper

    _saved = {
        "dbMap":          _srv.dbMap.copy(),
        "preparationMap": _srv.preparationMap.copy(),
        "botMap":         _srv.botMap.copy(),
        "_appConfig":     _srv._appConfig,
    }
    # TelegramMailingHelper.__init__ registers OS signal handlers; save them
    # so they can be restored after the test and don't affect other tests that
    # verify which helper is wired to SIGINT/SIGHUP.
    _saved_signals = {
        sig: _signal.getsignal(sig)
        for sig in (_signal.SIGINT, _signal.SIGTERM, _signal.SIGABRT, _signal.SIGHUP)
    }
    old_argv = sys.argv[:]
    helpers  = []

    def _factory(config_dict: dict, name: str = "cfg.json"):
        port = _free_port()
        cfg  = {
            "server":        {"port": port, "host": "localhost", "engine": "wsgiref"},
            "logFileName":   str(tmp_path / "helper.log"),
            "logOnlyInFile": False,
            **config_dict,
        }
        config_file = str(tmp_path / name)
        Path(config_file).write_text(json.dumps(cfg))

        sys.argv = [old_argv[0], config_file]
        app_config = prepareAndGetConfigOnly()
        helper     = TelegramMailingHelper(app_config)
        helpers.append(helper)
        return helper, config_file

    yield _factory

    for h in helpers:
        for bot in list(h.telegramBotList.values()):
            try:
                bot.stop()
            except Exception:
                pass

    _srv.dbMap          = _saved["dbMap"]
    _srv.preparationMap = _saved["preparationMap"]
    _srv.botMap         = _saved["botMap"]
    _srv._appConfig     = _saved["_appConfig"]

    for sig, handler in _saved_signals.items():
        _signal.signal(sig, handler)

    sys.argv = old_argv


# ── Tests: auth routing ───────────────────────────────────────────────────────

class TestAuthRouting:
    """HTTP Basic Auth must map each credential set to its own bot."""

    def test_alpha_app_info_returns_alpha_bot_name(self, multi_bot_server):
        resp = _api(multi_bot_server["base_url"], CREDS_ALPHA).get("/api/app-info")
        assert resp.status_code == 200
        assert resp.json()["botName"] == BOT_NAME_ALPHA

    def test_beta_app_info_returns_beta_bot_name(self, multi_bot_server):
        resp = _api(multi_bot_server["base_url"], CREDS_BETA).get("/api/app-info")
        assert resp.status_code == 200
        assert resp.json()["botName"] == BOT_NAME_BETA

    def test_wrong_credentials_rejected(self, multi_bot_server):
        resp = _api(multi_bot_server["base_url"], ("nobody", "wrong")).get("/api/app-info")
        assert resp.status_code == 401

    def test_no_credentials_rejected(self, multi_bot_server):
        resp = _http.get(f"{multi_bot_server['base_url']}/api/app-info", timeout=5)
        assert resp.status_code == 401


# ── Tests: data isolation ─────────────────────────────────────────────────────

class TestDataIsolation:
    """Users and dispatch lists must be strictly separated between bots."""

    def test_user_via_alpha_webhook_not_visible_to_beta(self, multi_bot_server):
        base     = multi_bot_server["base_url"]
        chat_id  = 30_000_001

        resp = _post_webhook(base, BOT_NAME_ALPHA, TOKEN_ALPHA, _make_start(chat_id))
        assert resp.status_code == 200

        found = wait_for(
            lambda: multi_bot_server["dao_alpha"]
                    .getUserByTelegramId(str(chat_id)) is not None,
            timeout=5,
        )
        assert found, "User not saved to alpha DB after /start via alpha webhook"
        assert multi_bot_server["dao_beta"].getUserByTelegramId(str(chat_id)) is None, \
            "User leaked into beta DB"

    def test_user_via_beta_webhook_not_visible_to_alpha(self, multi_bot_server):
        base    = multi_bot_server["base_url"]
        chat_id = 30_000_002

        resp = _post_webhook(base, BOT_NAME_BETA, TOKEN_BETA, _make_start(chat_id))
        assert resp.status_code == 200

        found = wait_for(
            lambda: multi_bot_server["dao_beta"]
                    .getUserByTelegramId(str(chat_id)) is not None,
            timeout=5,
        )
        assert found, "User not saved to beta DB"
        assert multi_bot_server["dao_alpha"].getUserByTelegramId(str(chat_id)) is None, \
            "User leaked into alpha DB"

    def test_alpha_users_list_contains_only_alpha_users(self, multi_bot_server):
        base    = multi_bot_server["base_url"]
        chat_id = 30_000_003

        _post_webhook(base, BOT_NAME_ALPHA, TOKEN_ALPHA, _make_start(chat_id))
        wait_for(
            lambda: multi_bot_server["dao_alpha"]
                    .getUserByTelegramId(str(chat_id)) is not None,
            timeout=5,
        )

        alpha_ids = {u["telegram_id"]
                     for u in _api(base, CREDS_ALPHA).get("/api/users-list").json()}
        beta_ids  = {u["telegram_id"]
                     for u in _api(base, CREDS_BETA).get("/api/users-list").json()}

        assert str(chat_id) in alpha_ids,  "Alpha user missing from alpha users-list"
        assert str(chat_id) not in beta_ids, "Alpha user visible in beta users-list"

    def test_dispatch_list_added_via_alpha_not_in_beta(self, multi_bot_server):
        base = multi_bot_server["base_url"]

        resp = _api(base, CREDS_ALPHA).post_form("/api/lists/add", {
            "name": "Alpha-Only List", "description": "isolation test",
            "list": "a1\na2\na3", "groupSize": "3", "repeatTimes": "1",
            "disableByDefault": "", "showCommentWithBlock": "",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        wait_for(
            lambda: len(list(multi_bot_server["dao_alpha"].getAllDispatchGroupNames())) > 0,
            timeout=10,
        )

        alpha_names = {g.dispatch_group_name
                       for g in multi_bot_server["dao_alpha"].getAllDispatchGroupNames()}
        beta_names  = {g.dispatch_group_name
                       for g in multi_bot_server["dao_beta"].getAllDispatchGroupNames()}

        assert "Alpha-Only List" in alpha_names, "List not found in alpha DB"
        assert "Alpha-Only List" not in beta_names, "Alpha list leaked into beta DB"


# ── Tests: webhook routing ────────────────────────────────────────────────────

class TestWebhookRouting:
    """Webhook endpoint must reject mismatched bot_name/token combos."""

    def test_wrong_token_for_alpha_rejected(self, multi_bot_server):
        resp = _post_webhook(multi_bot_server["base_url"],
                             BOT_NAME_ALPHA, "0:wrong_token", _make_start(39_000_001))
        assert resp.status_code in (400, 500)

    def test_alpha_token_on_beta_name_rejected(self, multi_bot_server):
        resp = _post_webhook(multi_bot_server["base_url"],
                             BOT_NAME_BETA, TOKEN_ALPHA, _make_start(39_000_002))
        assert resp.status_code in (400, 500)

    def test_beta_token_on_alpha_name_rejected(self, multi_bot_server):
        resp = _post_webhook(multi_bot_server["base_url"],
                             BOT_NAME_ALPHA, TOKEN_BETA, _make_start(39_000_003))
        assert resp.status_code in (400, 500)

    def test_unknown_bot_name_rejected(self, multi_bot_server):
        resp = _post_webhook(multi_bot_server["base_url"],
                             "no_such_bot", TOKEN_ALPHA, _make_start(39_000_004))
        assert resp.status_code in (400, 500)


# ── Tests: concurrent webhooks ────────────────────────────────────────────────

class TestConcurrentWebhooks:
    """Both bots must handle simultaneous updates without cross-contamination."""

    def test_simultaneous_start_commands_land_in_correct_dbs(self, multi_bot_server):
        import threading

        base    = multi_bot_server["base_url"]
        chat_a  = 40_000_001
        chat_b  = 40_000_002
        results = {}

        def _send_alpha():
            results["alpha"] = _post_webhook(
                base, BOT_NAME_ALPHA, TOKEN_ALPHA, _make_start(chat_a))

        def _send_beta():
            results["beta"] = _post_webhook(
                base, BOT_NAME_BETA, TOKEN_BETA, _make_start(chat_b))

        t_a = threading.Thread(target=_send_alpha)
        t_b = threading.Thread(target=_send_beta)
        t_a.start(); t_b.start()
        t_a.join();  t_b.join()

        assert results["alpha"].status_code == 200
        assert results["beta"].status_code  == 200

        assert wait_for(
            lambda: multi_bot_server["dao_alpha"]
                    .getUserByTelegramId(str(chat_a)) is not None, timeout=5), \
            "Alpha user missing after concurrent /start"
        assert wait_for(
            lambda: multi_bot_server["dao_beta"]
                    .getUserByTelegramId(str(chat_b)) is not None, timeout=5), \
            "Beta user missing after concurrent /start"

        assert multi_bot_server["dao_beta"].getUserByTelegramId(str(chat_a)) is None, \
            "Alpha user leaked into beta DB during concurrent processing"
        assert multi_bot_server["dao_alpha"].getUserByTelegramId(str(chat_b)) is None, \
            "Beta user leaked into alpha DB during concurrent processing"


# ── Tests: user confirmation notifies correct bot ─────────────────────────────

class TestUserConfirmationNotifiesCorrectBot:
    """Confirming a user must send the congratulation via that user's bot."""

    def test_confirming_alpha_user_uses_alpha_bot(self, multi_bot_server):
        from telegram_mailing_help.db.dao import User, UserState

        base      = multi_bot_server["base_url"]
        dao_alpha = multi_bot_server["dao_alpha"]
        tg_mock   = multi_bot_server["tg_mock"]

        chat_id = 50_000_001
        user = dao_alpha.saveUser(User(
            id=None, telegram_id=str(chat_id), name="Alpha Confirm",
            state=UserState.NEW.value, created=datetime.now().isoformat(),
        ))

        tg_mock.reset_calls()

        resp = _api(base, CREDS_ALPHA).post("/api/users/state/change", {"id": user.id})
        assert resp.status_code == 200
        assert resp.json()["state"] == UserState.CONFIRMED.value

        assert wait_for(lambda: tg_mock.calls_for("sendMessage") != [], timeout=5), \
            "No sendMessage after confirming alpha user"
        tg_mock.assert_message_sent_to(chat_id)
        tg_mock.assert_message_text_contains(chat_id, "Поздравляю")

    def test_confirming_beta_user_uses_beta_bot(self, multi_bot_server):
        from telegram_mailing_help.db.dao import User, UserState

        base     = multi_bot_server["base_url"]
        dao_beta = multi_bot_server["dao_beta"]
        tg_mock  = multi_bot_server["tg_mock"]

        chat_id = 50_000_002
        user = dao_beta.saveUser(User(
            id=None, telegram_id=str(chat_id), name="Beta Confirm",
            state=UserState.NEW.value, created=datetime.now().isoformat(),
        ))

        tg_mock.reset_calls()

        resp = _api(base, CREDS_BETA).post("/api/users/state/change", {"id": user.id})
        assert resp.status_code == 200
        assert resp.json()["state"] == UserState.CONFIRMED.value

        assert wait_for(lambda: tg_mock.calls_for("sendMessage") != [], timeout=5), \
            "No sendMessage after confirming beta user"
        tg_mock.assert_message_sent_to(chat_id)
        tg_mock.assert_message_text_contains(chat_id, "Поздравляю")


# ── Tests: config parsing ─────────────────────────────────────────────────────

class TestConfigParsing:
    """
    TelegramMailingHelper correctly identifies the operating mode from config
    and raises RuntimeError for invalid combinations.
    """

    def test_multi_bot_helper_has_one_bot_per_token(self, multi_bot_server):
        """The module fixture created exactly two bots — one per telegramTokens entry."""
        helper = multi_bot_server["helper"]
        assert set(helper.telegramBotList.keys()) == {BOT_NAME_ALPHA, BOT_NAME_BETA}
        assert set(helper.daoList.keys())         == {BOT_NAME_ALPHA, BOT_NAME_BETA}
        assert set(helper.preparationList.keys()) == {BOT_NAME_ALPHA, BOT_NAME_BETA}

    def test_multi_bot_helper_appconfig_has_correct_tokens(self, multi_bot_server):
        """appConfig.telegramTokens contains the right tokens for each bot."""
        cfg = multi_bot_server["helper"].appConfig
        assert cfg.telegramToken is None, \
            "telegramToken must be None in multi-bot mode"
        assert cfg.telegramTokens[BOT_NAME_ALPHA].token == TOKEN_ALPHA
        assert cfg.telegramTokens[BOT_NAME_BETA].token  == TOKEN_BETA

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_single_mode_helper_has_exactly_one_bot(self, make_helper, tmp_path):
        """telegramToken set + empty telegramTokens → exactly one bot with SINGLE_MODE key.

        Single-mode means polling (webHookMode=False); the mock returns True for
        getUpdates which triggers a harmless TypeError in the updater thread.
        """
        from telegram_mailing_help.appConfig import SINGLE_MODE_CONST

        helper, _ = make_helper({
            "db":             {"dbFile": str(tmp_path / "s.db")},
            "rootConfigDir":  str(tmp_path) + "/",
            "telegramToken":  "9999999999:single_mode_token",
            "telegramTokens": {},
            "telegramWebhookURL": "http://localhost",
        })

        assert list(helper.telegramBotList.keys()) == [SINGLE_MODE_CONST]
        assert helper.appConfig.telegramToken is not None

    def test_both_token_fields_set_raises(self, tmp_path):
        """Setting both telegramToken and telegramTokens raises RuntimeError."""
        from telegram_mailing_help.appConfig import ApplicationConfiguration, Token
        from telegram_mailing_help.db.config import Configuration as DbConfig
        from telegram_mailing_help.web.config import Configuration as WebCfg
        from telegram_mailing_help.telegramMailingHelper import TelegramMailingHelper

        cfg = ApplicationConfiguration(
            rootConfigDir=str(tmp_path) + "/",
            telegramToken="111:token",
            telegramTokens={"bot1": Token(token="222:also", logins=[])},
            db=DbConfig(dbFile=str(tmp_path / "x.db")),
            server=WebCfg(),
            logFileName=str(tmp_path / "log.txt"),
        )
        with pytest.raises(RuntimeError, match="wrong parameters"):
            TelegramMailingHelper(cfg)

    def test_neither_token_field_set_raises(self, tmp_path):
        """Setting neither telegramToken nor telegramTokens raises RuntimeError."""
        from telegram_mailing_help.appConfig import ApplicationConfiguration
        from telegram_mailing_help.db.config import Configuration as DbConfig
        from telegram_mailing_help.web.config import Configuration as WebCfg
        from telegram_mailing_help.telegramMailingHelper import TelegramMailingHelper

        cfg = ApplicationConfiguration(
            rootConfigDir=str(tmp_path) + "/",
            telegramToken=None,
            telegramTokens={},
            db=DbConfig(dbFile=str(tmp_path / "x.db")),
            server=WebCfg(),
            logFileName=str(tmp_path / "log.txt"),
        )
        with pytest.raises(RuntimeError, match="wrong parameters"):
            TelegramMailingHelper(cfg)


# ── Tests: signal handlers ────────────────────────────────────────────────────

class TestSignalHandlers:
    """
    TelegramMailingHelper registers OS signal handlers and their callbacks
    behave correctly.
    """

    def test_stop_signal_handlers_registered_for_sigint_sigterm(
            self, multi_bot_server):
        """
        In wsgiref mode the standard signal() function is used; SIGINT and
        SIGTERM must be wired to the multi-bot helper's signal_stop_handler.

        Bound methods are created fresh on every attribute access, so we
        compare .__self__ (the instance) rather than using `is`.
        """
        helper = multi_bot_server["helper"]
        for sig in (_signal.SIGINT, _signal.SIGTERM):
            handler = _signal.getsignal(sig)
            assert callable(handler), f"No callable registered for {sig}"
            assert handler.__self__ is helper, \
                f"signal {sig} is registered on a different helper instance"
            assert handler.__func__ is type(helper).signal_stop_handler

    def test_sighup_handler_registered(self, multi_bot_server):
        """SIGHUP must be wired to helper.signal_reload_handler."""
        helper  = multi_bot_server["helper"]
        handler = _signal.getsignal(_signal.SIGHUP)
        assert callable(handler)
        assert handler.__self__ is helper
        assert handler.__func__ is type(helper).signal_reload_handler

    def test_stop_handler_stops_all_bots(self, make_helper, tmp_path, tg_mock):
        """
        gevent_signal_stop_handler() must call stop() on every registered bot
        and then call sys.exit().

        The bot is created in webhook mode (telegramToken=None) so that
        bot.stop() calls dispatcher.stop() instead of starting a polling loop.
        setWebhook / deleteWebhook go through requests.post (layer-1 mock),
        not through the python-telegram-bot library (layer-2), so we check
        layer-1 calls via tg_mock._rsps.calls.
        """
        token = "3333333333:CCstop_test_token"
        helper, _ = make_helper({
            "db":             {"dbFile": str(tmp_path / "stop.db")},
            "rootConfigDir":  str(tmp_path) + "/",
            "telegramToken":  None,           # webhook mode
            "telegramTokens": {
                "stop_bot": {
                    "token":  token,
                    "logins": [{"user": "u", "password": "p"}],
                },
            },
            "telegramWebhookURL": "http://localhost",
        })

        tg_mock.reset_calls()
        with patch("sys.exit") as mock_exit:
            helper.gevent_signal_stop_handler()

        mock_exit.assert_called_once()

        # deleteWebhook is called via raw requests.post (layer 1); verify it
        # appeared in the responses mock's call log.
        delete_wh = [c for c in tg_mock._rsps.calls
                     if "deleteWebhook" in c.request.url]
        assert delete_wh, "deleteWebhook not recorded in layer-1 mock — bot.stop() was not called"

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_reload_handler_in_single_mode_is_noop(self, make_helper, tmp_path):
        """
        In SINGLE_MODE, gevent_signal_reload_handler must log a skip message
        and leave telegramBotList unchanged.

        Single-mode means telegramToken is set → webHookMode=False (polling).
        The mock returns True for getUpdates which causes a harmless TypeError
        in the updater thread; the warning is suppressed here.
        """
        from telegram_mailing_help.appConfig import SINGLE_MODE_CONST

        token = "4444444444:DDreload_noop_token"
        helper, _ = make_helper({
            "db":             {"dbFile": str(tmp_path / "noop.db")},
            "rootConfigDir":  str(tmp_path) + "/",
            "telegramToken":  token,
            "telegramTokens": {},
            "telegramWebhookURL": "http://localhost",
        })

        bots_before = set(helper.telegramBotList.keys())
        helper.gevent_signal_reload_handler()
        bots_after = set(helper.telegramBotList.keys())

        assert bots_before == bots_after == {SINGLE_MODE_CONST}, \
            "Single-mode reload must not change the bot list"

    def test_reload_handler_adds_new_bot(self, multi_bot_server, tg_mock):
        """
        Updating the config file to add a third bot and calling
        gevent_signal_reload_handler() must start that bot and add it to
        telegramBotList.
        """
        import copy, json as _json

        helper      = multi_bot_server["helper"]
        config_file = multi_bot_server["config_file"]
        base_url    = multi_bot_server["base_url"]
        data_dir    = multi_bot_server["data_dir"]
        port        = multi_bot_server["port"]

        token_gamma  = "5555555555:EEnew_gamma_bot"
        bot_gamma    = "bot_gamma"

        # Read current config and add bot_gamma
        current_cfg  = _json.loads(Path(config_file).read_text())
        new_cfg      = copy.deepcopy(current_cfg)
        new_cfg["telegramTokens"][bot_gamma] = {
            "token":  token_gamma,
            "logins": [{"user": "admin_gamma", "password": "pass_gamma"}],
        }
        Path(config_file).write_text(_json.dumps(new_cfg))

        tg_mock.reset_calls()
        helper.gevent_signal_reload_handler()

        assert wait_for(
            lambda: bot_gamma in helper.telegramBotList,
            timeout=5,
        ), "bot_gamma not added to telegramBotList after reload"
        # setWebhook is called via requests.post (layer-1), not through the
        # python-telegram-bot library, so it is not visible via calls_for().
        # Presence in telegramBotList is the authoritative confirmation that
        # prepareBotForStart completed (which calls bot.start → setWebhook).

        # Restore original config and remove the new bot for other tests
        Path(config_file).write_text(_json.dumps(current_cfg))
        if bot_gamma in helper.telegramBotList:
            helper.stopBot(bot_gamma)
            helper.appConfig.telegramTokens.pop(bot_gamma, None)

    def test_reload_handler_skips_already_running_bots(self, multi_bot_server):
        """
        Calling gevent_signal_reload_handler() without any config changes must
        NOT restart the existing bots — only log 'already loaded'.
        """
        helper = multi_bot_server["helper"]

        bots_before = set(helper.telegramBotList.keys())
        # Call reload with the unchanged config (sys.argv still points at config_file)
        helper.gevent_signal_reload_handler()
        bots_after = set(helper.telegramBotList.keys())

        assert bots_before == bots_after, \
            "Reload without config changes must not alter the running bot set"

    def test_reload_handler_removes_stopped_bot(self, multi_bot_server, tg_mock):
        """
        Removing a bot from the config file and calling
        gevent_signal_reload_handler() must stop and deregister that bot.
        """
        import copy, json as _json

        helper      = multi_bot_server["helper"]
        config_file = multi_bot_server["config_file"]

        # Write config with only bot_alpha (remove bot_beta)
        current_cfg = _json.loads(Path(config_file).read_text())
        reduced_cfg = copy.deepcopy(current_cfg)
        reduced_cfg["telegramTokens"] = {
            BOT_NAME_ALPHA: current_cfg["telegramTokens"][BOT_NAME_ALPHA],
        }
        Path(config_file).write_text(_json.dumps(reduced_cfg))

        tg_mock.reset_calls()
        helper.gevent_signal_reload_handler()

        assert wait_for(
            lambda: BOT_NAME_BETA not in helper.telegramBotList,
            timeout=5,
        ), "bot_beta was not removed from telegramBotList after reload"

        # Restore original config and re-add bot_beta so other tests still work
        Path(config_file).write_text(_json.dumps(current_cfg))
        helper.appConfig.telegramTokens = {
            k: v for k, v in helper.appConfig.telegramTokens.items()
        }
        # Re-add beta (without full restart) if it was removed
        if BOT_NAME_BETA not in helper.daoList:
            import telegram_mailing_help.web.server as _srv
            from telegram_mailing_help.db.config import Configuration as DbConfig
            from telegram_mailing_help.db.migration import Migration
            from telegram_mailing_help.db.dao import Dao
            from telegram_mailing_help.logic.listPreparation import Preparation
            from telegram_mailing_help.telegram.bot import MailingBot
            import copy as _copy

            cfg_beta    = _copy.deepcopy(helper.appConfig)
            cfg_beta.db = DbConfig(dbFile=multi_bot_server["db_beta"])
            dao_beta    = Dao(cfg_beta, BOT_NAME_BETA)
            prep_beta   = Preparation(cfg_beta, dao_beta)
            bot_beta    = MailingBot(
                botName=BOT_NAME_BETA, telegramToken=TOKEN_BETA,
                webHookMode=True, telegramWebhookURL=multi_bot_server["base_url"],
                db=dao_beta, preparation=prep_beta,
            )
            bot_beta.start()
            helper.daoList[BOT_NAME_BETA]         = dao_beta
            helper.preparationList[BOT_NAME_BETA] = prep_beta
            helper.telegramBotList[BOT_NAME_BETA] = bot_beta
            _srv.dbMap[BOT_NAME_BETA]             = dao_beta
            _srv.preparationMap[BOT_NAME_BETA]    = prep_beta
            _srv.botMap[BOT_NAME_BETA]            = bot_beta
