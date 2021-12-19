# -*- coding: utf-8 -*-
from selenium.webdriver import DesiredCapabilities
from testcontainers.selenium import BrowserWebDriverContainer


def test_for_test():
    with BrowserWebDriverContainer(DesiredCapabilities.CHROME).with_kwargs(
            extra_hosts={"host.docker.internal": "host-gateway"}) as chrome:
        webdriver = chrome.get_driver()
        webdriver.get("http://host.docker.internal:23445/pages/dispatch_lists.html")
        # webdriver.find_element_by_name("q").send_keys("Hello")
        webdriver.get_screenshot_as_file("/tmp/screenshot.png")
