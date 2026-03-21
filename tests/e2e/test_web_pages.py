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
    # Vue Router (hash history) redirects / → /#/dispatch_lists
    expect(page).to_have_url("/#/dispatch_lists")


def test_dispatch_lists_page_loads(page: Page):
    page.goto("/#/dispatch_lists")
    expect(page).to_have_title("Рассылки: админка")
    # Two tab links should be visible: "Текущие рассылки" and "Добавить новую"
    tabs = page.locator("a.u-tab-link")
    expect(tabs.first).to_be_visible()
    expect(tabs).to_have_count(2)


def test_users_page_loads(page: Page):
    page.goto("/#/users")
    # Vue renders the table once /api/users-list responds
    expect(page.locator("table.u-table-entity")).to_be_visible(timeout=10_000)


def test_settings_page_loads(page: Page):
    page.goto("/#/settings")
    expect(page.locator("table.u-table-entity")).to_be_visible(timeout=10_000)


def test_reports_page_loads(page: Page):
    page.goto("/#/reports")
    expect(page.locator("body")).to_be_visible()


# ---------------------------------------------------------------------------
# Header navigation menu
# ---------------------------------------------------------------------------

def test_nav_menu_visible_on_desktop(page: Page):
    """Desktop nav links are visible in the header without opening any hamburger."""
    page.goto("/#/dispatch_lists")
    nav = page.locator("nav.u-menu .u-nav-container")
    expect(nav).to_be_visible()
    # All four route links are rendered inside the desktop container
    links = nav.locator("a.u-nav-link")
    expect(links).to_have_count(4)


def test_nav_links_navigate_between_pages(page: Page):
    """Clicking each nav link routes to the correct hash URL and renders its page."""
    page.goto("/#/dispatch_lists")

    # Navigate to Users via nav link
    page.locator("nav .u-nav-container a.u-nav-link", has_text="Пользователи").click()
    expect(page).to_have_url("/#/users")
    expect(page.locator("table.u-table-entity")).to_be_visible(timeout=10_000)

    # Navigate to Settings
    page.locator("nav .u-nav-container a.u-nav-link", has_text="Настройки").click()
    expect(page).to_have_url("/#/settings")
    expect(page.locator("table.u-table-entity")).to_be_visible(timeout=10_000)

    # Navigate to Reports
    page.locator("nav .u-nav-container a.u-nav-link", has_text="Отчеты").click()
    expect(page).to_have_url("/#/reports")
    expect(page.locator("body")).to_be_visible()

    # Navigate back to Dispatch lists
    page.locator("nav .u-nav-container a.u-nav-link", has_text="Редактирование списков").click()
    expect(page).to_have_url("/#/dispatch_lists")
    expect(page.locator("a.u-tab-link").first).to_be_visible()


# ---------------------------------------------------------------------------
# Dispatch list form interaction
# ---------------------------------------------------------------------------

def test_add_dispatch_list_via_ui(page: Page):
    page.goto("/#/dispatch_lists")

    # Switch to "Добавить новую" tab (second tab link)
    page.locator("a.u-tab-link", has_text="Добавить новую").click()

    form = page.locator("form.u-inner-form")
    expect(form).to_be_visible()

    # Fill required fields
    page.fill("input[placeholder*='Название']", "UI Test List")
    page.fill("input[placeholder*='Описание']", "Created by Playwright")
    page.fill("textarea[placeholder*='список']", "item1\nitem2\nitem3\nitem4\nitem5")
    page.locator("input[list='groupSizeVariants']").fill("5")
    page.locator("input[list='repeatTimesVariants']").fill("1")

    # Submit the form
    page.locator("button[type='submit']").click()

    # SweetAlert2 progress dialog should appear
    expect(page.locator(".swal2-popup")).to_be_visible(timeout=10_000)
