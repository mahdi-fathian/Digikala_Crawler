from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(record_har_path="digikala_network.har")
    page = context.new_page()
    page.goto("https://www.digikala.com/search/category-mobile-phone/")
    print("لطفاً صفحه را اسکرول کنید تا محصولات بیشتری لود شوند...")
    page.wait_for_timeout(20000)  # 20 ثانیه برای اسکرول و لود کامل
    context.close()
    browser.close()
print("فایل HAR با موفقیت ذخیره شد: digikala_network.har") 