import json
import re

# مسیر فایل HAR
HAR_FILE = 'digikala_network.har'

# کلیدواژه‌های endpoint محصولات
PRODUCT_ENDPOINTS = [
    'product-list',
    'providers-products',
    'search',
    'category',
]

with open(HAR_FILE, 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har.get('log', {}).get('entries', [])
product_xhrs = []

for entry in entries:
    req = entry.get('request', {})
    url = req.get('url', '')
    if any(ep in url for ep in PRODUCT_ENDPOINTS):
        method = req.get('method', '')
        headers = {h['name']: h['value'] for h in req.get('headers', [])}
        query = req.get('queryString', [])
        params = {q['name']: q['value'] for q in query}
        resp = entry.get('response', {})
        status = resp.get('status', 0)
        content = resp.get('content', {})
        mime = content.get('mimeType', '')
        text = content.get('text', '')
        if status == 200 and 'json' in mime and len(text) > 100:
            product_xhrs.append({
                'url': url,
                'method': method,
                'headers': headers,
                'params': params,
                'sample_response': text[:1000],
            })
            # ذخیره کامل response برای بررسی دقیق
            with open('full_product_xhr_response.json', 'w', encoding='utf-8') as f:
                f.write(text)

with open('extracted_product_xhrs.json', 'w', encoding='utf-8') as f:
    json.dump(product_xhrs, f, ensure_ascii=False, indent=2)

print(f'تعداد XHR محصولات یافت شده: {len(product_xhrs)}')
print('نمونه‌ها در extracted_product_xhrs.json ذخیره شد.') 