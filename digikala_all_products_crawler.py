import requests
import json
import pandas as pd
import time

with open('digikala_category_codes.json', 'r', encoding='utf-8') as f:
    categories = json.load(f)

HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'origin': 'https://www.digikala.com',
    'referer': 'https://www.digikala.com/',
    'x-web-client': 'desktop',
    'x-web-optimize-response': '1',
}
COOKIES = {
    # کوکی‌های مهم را در صورت نیاز قرار دهید
}

all_products = []
all_ads = []

for cat in categories:
    print(f'--- دسته‌بندی: {cat} ---')
    for page in range(1, 6):  # هر دسته 5 صفحه (قابل افزایش)
        url = f'https://api.digikala.com/v1/categories/{cat}/search/'
        params = {'page': page}
        resp = requests.get(url, headers=HEADERS, cookies=COOKIES, params=params)
        if resp.status_code != 200:
            print(f'خطا در {cat} صفحه {page}: {resp.status_code}')
            break
        data = resp.json()
        products = data.get('data', {}).get('products', [])
        if not products:
            break
        for p in products:
            img_url = ''
            images = p.get('images', {})
            if isinstance(images, dict):
                urls = images.get('main', {}).get('url', [])
                img_url = urls[0] if urls else ''
            item = {
                'نام': p.get('title_fa', ''),
                'قیمت': p.get('default_variant', {}).get('price', {}).get('selling_price', 0),
                'برند': p.get('brand', {}).get('title_fa', ''),
                'امتیاز': p.get('rating', {}).get('rate', 0),
                'تعداد_نظرات': p.get('rating', {}).get('count', 0),
                'آدرس': f"https://www.digikala.com{p.get('url', {}).get('uri', '')}",
                'تصویر': img_url,
                'دسته': cat,
                'تبلیغاتی': p.get('is_ad', False)
            }
            if item['تبلیغاتی']:
                all_ads.append(item)
            else:
                all_products.append(item)
        time.sleep(1)

# حذف خروجی‌های خالی قبلی
import os
for fname in [
    'digikala_products_full.json',
    'digikala_products_providers.json',
    'digikala_products_cookie.json',
    'digikala_real_products.json',
    'digikala_real_products.csv',
    'digikala_products.csv',
    'digikala_reviews.csv',
]:
    if os.path.exists(fname) and os.path.getsize(fname) < 1000:
        os.remove(fname)

# ذخیره محصولات واقعی
with open('digikala_all_products.json', 'w', encoding='utf-8') as f:
    json.dump(all_products, f, ensure_ascii=False, indent=4)
if all_products:
    pd.DataFrame(all_products).to_csv('digikala_all_products.csv', index=False, encoding='utf-8-sig')

# ذخیره تبلیغاتی‌ها
with open('digikala_all_ads.json', 'w', encoding='utf-8') as f:
    json.dump(all_ads, f, ensure_ascii=False, indent=4)
if all_ads:
    pd.DataFrame(all_ads).to_csv('digikala_all_ads.csv', index=False, encoding='utf-8-sig')

print(f'تعداد محصولات واقعی: {len(all_products)}')
print(f'تعداد محصولات تبلیغاتی: {len(all_ads)}')
print('خروجی‌ها با موفقیت ذخیره شدند.') 