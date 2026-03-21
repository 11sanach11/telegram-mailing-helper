"""
Telegram Bot API HTTP-level mock — analogous to Spring's MockRestServiceServer.

python-telegram-bot v13 uses a *bundled* urllib3 (`telegram.vendor.ptb_urllib3`)
instead of the standard `requests` library for its API calls.  This means
generic HTTP-mocking libraries (e.g. `responses`) cannot intercept them.

The solution is a two-layer mock:

  Layer 1 — `responses` library
      Intercepts calls made via the standard `requests` library.  Our own
      application code in bot.py calls `requests.post(setWebhook/deleteWebhook
      URL)` directly, so these land here.

  Layer 2 — `telegram.utils.request.Request.post` patch
      Intercepts all outbound Telegram Bot API calls made by the
      python-telegram-bot library itself (sendMessage, answerCallbackQuery,
      getMe, …).  The method is patched at the class level so it takes effect
      in every thread (including the Dispatcher thread).

Together the two layers record every Telegram API interaction and let tests
assert on them using a simple helper API.

Usage
-----
    # In conftest (session scope):
    tg_mock = TelegramApiMock(token=TEST_TOKEN)
    tg_mock.start()
    # ... start the application server ...
    yield {"tg_mock": tg_mock, ...}
    tg_mock.stop()

    # In a test:
    tg_mock.reset_calls()
    post_webhook(...)              # trigger some bot interaction
    wait_for(lambda: tg_mock.calls_for("sendMessage"), timeout=5)
    tg_mock.assert_message_sent_to(chat_id=12345)
    tg_mock.assert_message_text_contains(12345, "Поздравляю")
"""
import json
import re
import threading
from typing import Any, Optional, Union

import responses as _r
from responses import RequestsMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TG_API_HOST = re.compile(r"https://api\.telegram\.org/.*")


def _tg_url(method: str, token: str) -> re.Pattern:
    """Regex matching  https://api.telegram.org/bot{token}/{method}[?...]"""
    return re.compile(
        r"https://api\.telegram\.org/bot"
        + re.escape(token)
        + r"/"
        + re.escape(method)
        + r"(\?.*)?"
    )


def _method_from_url(url: str) -> str:
    """Extract the API method name from a Telegram Bot API URL."""
    return url.split("/")[-1].split("?")[0]


# Return values for Request.post — these are the *unpacked* result values
# (what Telegram's {"ok": True, "result": <X>} contains as <X>).
# python-telegram-bot's _parse() already strips the envelope.

_FAKE_MESSAGE = {
    "message_id": 1,
    "from": {"id": 1234567890, "is_bot": True, "first_name": "TestBot", "username": "testbot"},
    "chat": {"id": 0, "type": "private"},
    "date": 1700000000,
    "text": "__mock__",
}

_FAKE_USER = {
    "id": 1234567890,
    "is_bot": True,
    "first_name": "TestBot",
    "username": "testbot",
}

# Map API method → return value for Request.post mock
_DEFAULT_RESULTS: dict[str, Any] = {
    "sendMessage": _FAKE_MESSAGE,
    "getMe": _FAKE_USER,
    "answerCallbackQuery": True,
    "setWebhook": True,
    "deleteWebhook": True,
    "forwardMessage": _FAKE_MESSAGE,
    "copyMessage": {"message_id": 2},
    "sendPhoto": _FAKE_MESSAGE,
    "sendDocument": _FAKE_MESSAGE,
    "sendSticker": _FAKE_MESSAGE,
    "sendAudio": _FAKE_MESSAGE,
    "sendVideo": _FAKE_MESSAGE,
    "sendVoice": _FAKE_MESSAGE,
    "editMessageText": _FAKE_MESSAGE,
    "editMessageReplyMarkup": _FAKE_MESSAGE,
    "deleteMessage": True,
    "getChatMember": {"status": "member", "user": _FAKE_USER},
    "kickChatMember": True,
    "unbanChatMember": True,
    "restrictChatMember": True,
}


# ---------------------------------------------------------------------------
# Call record
# ---------------------------------------------------------------------------

class TgCall:
    """A single recorded Telegram Bot API call."""

    def __init__(self, method: str, url: str, data: dict):
        self.method = method  # e.g. "sendMessage"
        self.url = url
        self.data = data  # request parameters dict

    def __repr__(self) -> str:
        return f"TgCall({self.method!r}, data={self.data!r})"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TelegramApiMock:
    """
    Two-layer Telegram Bot API mock.

    Active for the whole test session; call reset_calls() between tests to
    isolate recorded history.
    """

    def __init__(self, token: str):
        self.token = token
        self._calls: list[TgCall] = []
        self._lock = threading.Lock()

        # Layer 1: responses for standard `requests` library calls
        self._rsps = RequestsMock(
            assert_all_requests_are_fired=False,
            passthru_prefixes=("http://localhost", "http://127.0.0.1"),
        )

        # Layer 2: telegram.utils.request.Request.post patch (set in start())
        self._original_request_post = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "TelegramApiMock":
        """Activate both interception layers.  Call once before app startup."""
        self._start_responses_layer()
        self._start_request_patch_layer()
        return self

    def stop(self):
        """Deactivate both layers.  Call at session teardown."""
        self._stop_request_patch_layer()
        self._rsps.stop()
        self._rsps.reset()

    # ------------------------------------------------------------------
    # Layer 1: responses (for requests.post calls in our own code)
    # ------------------------------------------------------------------

    def _start_responses_layer(self):
        self._rsps.start()
        # Catch-all: any request.* call to telegram returns {"ok": true}
        for http_method in (_r.GET, _r.POST, _r.PUT, _r.DELETE, _r.PATCH, _r.HEAD, _r.OPTIONS):
            self._rsps.add(http_method, _TG_API_HOST, json={"ok": True, "result": True})

    # ------------------------------------------------------------------
    # Layer 2: patch telegram.utils.request.Request.post
    # ------------------------------------------------------------------

    def _start_request_patch_layer(self):
        from telegram.utils.request import Request

        self._original_request_post = Request.post
        mock_self = self  # closure reference

        def _patched_post(req_instance, url: str, data: dict, timeout=None) -> Union[dict, bool]:
            method = _method_from_url(url)
            with mock_self._lock:
                mock_self._calls.append(TgCall(method=method, url=url, data=dict(data or {})))
            result = _DEFAULT_RESULTS.get(method, True)
            # Return a copy so callers can't mutate the template
            return dict(result) if isinstance(result, dict) else result

        Request.post = _patched_post  # type: ignore[method-assign]

    def _stop_request_patch_layer(self):
        if self._original_request_post is not None:
            from telegram.utils.request import Request
            Request.post = self._original_request_post  # type: ignore[method-assign]
            self._original_request_post = None

    # ------------------------------------------------------------------
    # Call history
    # ------------------------------------------------------------------

    def reset_calls(self):
        """Clear recorded call history (use between tests)."""
        with self._lock:
            self._calls.clear()
        self._rsps.calls.reset()

    def calls_for(self, method: str) -> list[TgCall]:
        """Return all recorded calls to the given Telegram Bot API method."""
        with self._lock:
            return [c for c in self._calls if c.method == method]

    @property
    def all_calls(self) -> list[TgCall]:
        with self._lock:
            return list(self._calls)

    def sent_messages(self) -> list[dict]:
        """Return the data dicts of all sendMessage calls."""
        return [c.data for c in self.calls_for("sendMessage")]

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def assert_called(self, method: str, min_times: int = 1):
        """Assert that a Telegram API method was called at least *min_times*."""
        calls = self.calls_for(method)
        assert len(calls) >= min_times, (
            f"Expected Telegram API '{method}' to be called >= {min_times} time(s), "
            f"got {len(calls)}.  All calls: {[c.method for c in self.all_calls]}"
        )

    def assert_message_sent_to(self, chat_id: int | str):
        """Assert that at least one sendMessage was addressed to *chat_id*."""
        messages = self.sent_messages()
        actual_ids = [str(m.get("chat_id")) for m in messages]
        assert str(chat_id) in actual_ids, (
            f"Expected sendMessage to chat_id={chat_id}, "
            f"but calls went to: {actual_ids or '(none)'}"
        )

    def assert_message_text_contains(
        self,
        chat_id: int | str,
        substring: str,
        *,
        msg: Optional[str] = None,
    ):
        """Assert that a message sent to *chat_id* contains *substring*."""
        messages = [m for m in self.sent_messages() if str(m.get("chat_id")) == str(chat_id)]
        texts = [m.get("text", "") for m in messages]
        assert any(substring in t for t in texts), (
            msg
            or f"Expected a message to chat_id={chat_id} containing {substring!r}; "
               f"actual texts: {texts or '(none)'}"
        )

    def assert_no_messages_to(self, chat_id: int | str):
        """Assert that no sendMessage was addressed to *chat_id*."""
        actual_ids = [str(m.get("chat_id")) for m in self.sent_messages()]
        assert str(chat_id) not in actual_ids, (
            f"Expected NO sendMessage to chat_id={chat_id}, but one was sent"
        )
