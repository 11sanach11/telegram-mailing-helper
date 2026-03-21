"""
E2E API tests via Playwright's APIRequestContext.

Tests each REST endpoint directly with HTTP requests (no browser rendering).
"""
import time

import pytest
from playwright.sync_api import APIRequestContext, Playwright


@pytest.fixture(scope="module")
def api(playwright: Playwright, base_url) -> APIRequestContext:
    from tests.e2e.conftest import _HTTP_CREDENTIALS
    ctx = playwright.request.new_context(
        base_url=base_url,
        http_credentials=_HTTP_CREDENTIALS,
    )
    yield ctx
    ctx.dispose()


# ---------------------------------------------------------------------------
# /info
# ---------------------------------------------------------------------------

def test_info_returns_version(api: APIRequestContext):
    resp = api.get("/info")
    assert resp.status == 200
    body = resp.json()
    assert "version" in body
    assert body["app"] == "telegram_mailing_helper"


# ---------------------------------------------------------------------------
# Dispatch list API
# ---------------------------------------------------------------------------

def test_add_dispatch_list(api: APIRequestContext):
    resp = api.post("/api/lists/add", form={
        "name": "API Test List",
        "description": "test",
        "list": "a\nb\nc\nd\ne",
        "groupSize": "5",
        "repeatTimes": "1",
        "disableByDefault": "",
        "showCommentWithBlock": "",
    })
    assert resp.status == 200
    body = resp.json()
    assert body["success"] is True
    assert body.get("id") is not None


def test_get_list_state(api: APIRequestContext):
    # First create a list to get a valid state_id
    resp = api.post("/api/lists/add", form={
        "name": "State Test List",
        "description": "",
        "list": "x\ny\nz\nw\nv",
        "groupSize": "5",
        "repeatTimes": "1",
        "disableByDefault": "",
        "showCommentWithBlock": "",
    })
    state_id = resp.json()["id"]

    # Poll state endpoint
    resp = api.get(f"/api/lists/{state_id}/state")
    assert resp.status == 200
    body = resp.json()
    assert body.get("success") is True


def test_enable_and_disable_list(api: APIRequestContext, dao):
    # Find any existing dispatch group
    groups = list(dao.getAllDispatchGroupNames())
    assert groups, "Need at least one dispatch group (run test_add_dispatch_list first)"
    gr_id = groups[0].id

    # Disable
    resp = api.post(f"/api/lists/{gr_id}/state",
                    data='{"state":"disable"}',
                    headers={"Content-Type": "application/json"})
    assert resp.status == 200
    assert resp.json()["success"] is True

    # Enable
    resp = api.post(f"/api/lists/{gr_id}/state",
                    data='{"state":"enable"}',
                    headers={"Content-Type": "application/json"})
    assert resp.status == 200
    assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

def test_change_setting(api: APIRequestContext):
    import json as _json
    resp = api.post("/api/settings/change",
                    data=_json.dumps({"key": "admin_url", "value": "http://localhost:test"}),
                    headers={"Content-Type": "application/json"})
    assert resp.status == 200
    body = resp.json()
    assert body["success"] is True
    assert body["key"] == "admin_url"


# ---------------------------------------------------------------------------
# Users API
# ---------------------------------------------------------------------------

def test_change_user_state(api: APIRequestContext, dao):
    from datetime import datetime
    from telegram_mailing_help.db.dao import User, UserState
    import json as _json

    # Insert a user directly via DAO to have something to confirm
    user = dao.saveUser(User(
        id=None,
        telegram_id="999888777",
        name="API Test User",
        state=UserState.NEW.value,
        created=datetime.now().isoformat(),
    ))

    resp = api.post("/api/users/state/change",
                    data=_json.dumps({"id": user.id}),
                    headers={"Content-Type": "application/json"})
    assert resp.status == 200
    body = resp.json()
    assert body["success"] is True
    assert body["state"] == UserState.CONFIRMED.value
