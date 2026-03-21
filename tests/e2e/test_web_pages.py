"""
E2E browser tests via Playwright.

Covers navigation to every page and basic UI interaction (form submit for
adding a dispatch list).
"""
import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Page navigation
# ---------------------------------------------------------------------------

def test_root_redirects_to_dispatch_lists(page: Page):
    page.goto("/")
    expect(page).to_have_url("/pages/dispatch_lists.html")


def test_dispatch_lists_page_loads(page: Page):
    page.goto("/pages/dispatch_lists.html")
    expect(page).to_have_title("Disp: Списки")
    # Tab "Текущие рассылки" is present and active
    expect(page.locator("a#link-tab-081f")).to_be_visible()
    # Tab "Добавить новую" is present
    expect(page.locator("a#link-tab-4d57")).to_be_visible()


def test_users_page_loads(page: Page):
    page.goto("/pages/users.html")
    expect(page.locator("table.u-table-entity")).to_be_visible()


def test_settings_page_loads(page: Page):
    page.goto("/pages/settings.html")
    expect(page.locator("table.u-table-entity")).to_be_visible()


def test_reports_page_loads(page: Page):
    page.goto("/pages/reports.html")
    expect(page.locator("body")).to_be_visible()


# ---------------------------------------------------------------------------
# Dispatch list form interaction
# ---------------------------------------------------------------------------

def test_add_dispatch_list_via_ui(page: Page):
    page.goto("/pages/dispatch_lists.html")

    # Switch to the "Добавить новую" tab
    page.locator("a#link-tab-4d57").click()

    form = page.locator("#add-dispatch-list-form")
    expect(form).to_be_visible()

    # Fill required fields
    page.fill("input[name='name']", "UI Test List")
    page.fill("input[name='description']", "Created by Playwright")
    page.fill("textarea[name='list']", "item1\nitem2\nitem3\nitem4\nitem5")
    page.fill("input[name='groupSize']", "5")
    page.fill("input[name='repeatTimes']", "1")

    # Click the visible submit button (the <a> with u-btn-submit class)
    page.locator("a.u-btn-submit").click()

    # NicePage JS adds a second .u-form-send-success element dynamically with the
    # API response text (the first static one stays hidden). Use .last so
    # Playwright picks the newly visible element on each retry.
    expect(page.locator(".u-form-send-success").last).to_be_visible(timeout=10_000)
