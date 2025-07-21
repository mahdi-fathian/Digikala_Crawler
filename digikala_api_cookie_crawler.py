import requests
import json
import pandas as pd
import time

CATEGORY = 'mobile-phone'
MAX_PAGES = 20
BASE_URL = 'https://api.digikala.com/v1/providers-products/'

COOKIES = {
    'tracker_session': '7WWXNlo',
    'tracker_glob_new': 'fljauWa',
    'digikala-sp': '51f7d86a-6735-4df7-968c-c37e74ba6463',
    'device_id': 'a704bf3d-1b4d-4b5d-8707-7437073dfb82',
}
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'accept': 'application/json, text/plain, */*',
}

all_products = []
all_ads = []

for page in range(1, MAX_PAGES + 1):
    params = {
        'category_code': CATEGORY,
        'page': page,
    }
    print(f'در حال دریافت صفحه {page}...')
    resp = requests.get(BASE_URL, headers=HEADERS, cookies=COOKIES, params=params)
    if resp.status_code != 200:
        print(f'خطا در دریافت صفحه {page}: {resp.status_code}')
        print(resp.text[:500])
        break
    try:
        data = resp.json()
    except Exception as e:
        print(f'خطا در پارس JSON صفحه {page}: {e}')
        print('پاسخ دریافتی:')
        print(resp.text)
        break
    # محصولات واقعی
    products = data.get('data', [])
    print('ساختار data صفحه', page, ':', type(products), products if isinstance(products, (dict, list)) else str(products)[:500])
    for p in products:
        if not isinstance(p, dict):
            continue
        item = {
            'نام': p.get('title_fa', ''),
            'قیمت': p.get('default_variant', {}).get('price', {}).get('selling_price', 0),
            'برند': p.get('brand', {}).get('title_fa', ''),
            'امتیاز': p.get('rating', 0),
            'تعداد_نظرات': p.get('review', {}).get('count', 0),
            'آدرس': f"https://www.digikala.com/product/dkp-{p.get('id', '')}/",
            'تبلیغاتی': False
        }
        all_products.append(item)
    time.sleep(1)

with open('digikala_products_providers.json', 'w', encoding='utf-8') as f:
    json.dump({'products': all_products}, f, ensure_ascii=False, indent=4)

pd.DataFrame(all_products).to_csv('digikala_products_providers.csv', index=False, encoding='utf-8-sig')

print(f'تعداد محصولات واقعی: {len(all_products)}')
print('خروجی‌ها با موفقیت ذخیره شدند.') 