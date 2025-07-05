import pytest
from playwright.sync_api import Playwright, sync_playwright

@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p

@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()

@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()