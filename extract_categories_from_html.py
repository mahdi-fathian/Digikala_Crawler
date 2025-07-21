import re
import json

with open('digikala_page_source.html', 'r', encoding='utf-8') as f:
    html = f.read()

# استخراج همه category_codeها
pattern = r'/search/category-([a-zA-Z0-9\-]+)/'
codes = set(re.findall(pattern, html))

# نمایش و ذخیره
codes = sorted(codes)
print(f'تعداد دسته‌بندی یکتا: {len(codes)}')
for c in codes:
    print(c)

with open('digikala_category_codes.json', 'w', encoding='utf-8') as f:
    json.dump(codes, f, ensure_ascii=False, indent=2) 