import requests
import json

url = "https://api.digikala.com/v1/dictionaries/"
params = {'types[0]': 'category_tree'}
headers = {
    'accept': 'application/json, text/plain, */*',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'origin': 'https://www.digikala.com',
    'referer': 'https://www.digikala.com/',
    'x-web-client': 'desktop',
    'x-web-optimize-response': '1',
}

resp = requests.get(url, headers=headers, params=params)
if resp.status_code != 200:
    print('خطا در دریافت دسته‌بندی‌ها:', resp.status_code)
    print(resp.text[:500])
    exit(1)

data = resp.json()
with open('digikala_categories.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# نمایش ساختار دسته‌بندی‌ها
for d in data.get('data', []):
    if d.get('type') == 'category_tree':
        tree = d['data']['tree']
        def print_tree(node, level=0):
            print('  ' * level + f"- {node.get('title_fa', node.get('title_en', ''))} ({node.get('code', '')})")
            for child in node.get('children', []):
                print_tree(child, level+1)
        for cat in tree:
            print_tree(cat) 