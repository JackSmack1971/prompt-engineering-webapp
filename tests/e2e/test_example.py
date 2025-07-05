def test_example_ui(page):
    page.goto("https://www.google.com")  # Replace with your application's URL
    assert page.title() == "Google"