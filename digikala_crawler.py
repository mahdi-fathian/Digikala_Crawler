import scrapy
import json
import logging
import time
import sqlite3
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import concurrent.futures
import re
import random
import os
from typing import Dict, List, Optional
from scrapy.http import Response
from scrapy.exceptions import CloseSpider

# تنظیمات لاگینگ پیشرفته
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('digikala_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# تنظیمات پایگاه داده
Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    price = Column(Float)
    category = Column(String(100))
    url = Column(Text)
    description = Column(Text)
    rating = Column(Float)
    review_count = Column(Integer)
    image_url = Column(Text)
    specs = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer)
    product_url = Column(Text)
    comment = Column(Text)
    rating = Column(Float)
    date = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

class DigikalaSpider(scrapy.Spider):
    name = 'digikala_spider'
    allowed_domains = ['digikala.com']
    start_urls = ['https://www.digikala.com/']
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3.0,  # تاخیر 3 ثانیه بین درخواست‌ها
        'CONCURRENT_REQUESTS': 32,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'ROBOTSTXT_OBEY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 429],
        'FEEDS': {
            'digikala_products.json': {
                'format': 'json',
                'encoding': 'utf8',
                'store_empty': False,
                'indent': 4,
            }
        },
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
        }
    }
    
    def __init__(self, category_url: Optional[str] = None, resume_failed: bool = False):
        super().__init__()
        self.items_scraped = 0
        self.max_items = 5000  # حداکثر تعداد محصول
        self.start_time = time.time()
        self.failed_urls = []
        self.engine = create_engine('sqlite:///digikala.db')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.categories_scraped = set()
        self.category_url = category_url
        self.resume_failed = resume_failed

    def start_requests(self):
        """شروع خزیدن با توجه به پارامتر ورودی یا ادامه از خطاها"""
        if self.resume_failed and os.path.exists('failed_urls.txt'):
            with open('failed_urls.txt', 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            logger.info(f"Resume mode: خزیدن از {len(urls)} آدرس ناموفق قبلی")
            for url in urls:
                yield scrapy.Request(url=url, callback=self.parse)
        elif self.category_url:
            logger.info(f"خزیدن فقط از دسته‌بندی: {self.category_url}")
            yield scrapy.Request(url=self.category_url, callback=self.parse_category, meta={'category': 'Custom'})
        else:
            for url in self.start_urls:
                yield scrapy.Request(url=url, callback=self.parse)
            
    def parse(self, response: Response) -> None:
        """پارس کردن صفحه اصلی برای یافتن دسته‌بندی‌ها"""
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            # سلکتور جدید دسته‌بندی‌ها (بر اساس ساختار فعلی سایت)
            category_links = soup.select('a[data-testid="category-list-item"]')
            if not category_links:
                # fallback: جستجو برای لینک‌های دسته‌بندی در منوی اصلی
                category_links = soup.select('a[href*="/search/category-"]')
            for link in category_links:
                href = link.get('href')
                if href and '/search/category-' in href:
                    full_url = urljoin(response.url, href)
                    if full_url not in self.categories_scraped:
                        self.categories_scraped.add(full_url)
                        logger.info(f"دسته‌بندی جدید یافت شد: {full_url}")
                        yield scrapy.Request(
                            url=full_url,
                            callback=self.parse_category,
                            meta={'category': link.text.strip()}
                        )
        except Exception as e:
            logger.error(f"خطا در پارس صفحه اصلی: {str(e)}")
            self.failed_urls.append(response.url)
            
    def parse_category(self, response: Response) -> None:
        """پارس کردن صفحات دسته‌بندی برای یافتن محصولات"""
        try:
            category = response.meta.get('category', 'Unknown')
            soup = BeautifulSoup(response.text, 'html.parser')
            # سلکتور جدید کارت محصول (بر اساس ساختار فعلی سایت)
            products = soup.select('div[data-testid="product-card"]')
            if not products:
                # fallback: جستجو برای divهایی با لینک محصول
                products = soup.select('div.c-product-box')
            for product in products:
                if self.items_scraped >= self.max_items:
                    logger.info(f"به حداکثر تعداد محصول ({self.max_items}) رسیدیم")
                    raise CloseSpider('max_items_reached')
                item = self.parse_product(product, response.url, category)
                if item:
                    self.items_scraped += 1
                    yield scrapy.Request(
                        url=item['url'],
                        callback=self.parse_product_page,
                        meta={'item': item},
                        priority=10
                    )
            # یافتن صفحه بعدی
            next_page = soup.select_one('a[aria-label="صفحه بعد"]')
            if not next_page:
                next_page = soup.select_one('a[rel="next"]')
            if next_page and next_page.get('href'):
                next_page_url = urljoin(response.url, next_page['href'])
                logger.info(f"رفتن به صفحه بعدی: {next_page_url}")
                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse_category,
                    meta={'category': category}
                )
        except Exception as e:
            logger.error(f"خطا در پارس دسته‌بندی {response.url}: {str(e)}")
            self.failed_urls.append(response.url)
            
    def parse_product(self, product, base_url: str, category: str) -> Dict:
        """استخراج اطلاعات اولیه محصول با سلکتورهای جدید"""
        item = {}
        try:
            # نام محصول
            name = product.select_one('[data-testid="product-title"]')
            if not name:
                name = product.select_one('h3')
            item['name'] = name.text.strip() if name else 'N/A'
            # قیمت
            price = product.select_one('[data-testid="price-main"]')
            if not price:
                price = product.select_one('div.c-price__value')
            item['price'] = self.parse_price(price.text.strip()) if price else 0.0
            # لینک محصول
            link = product.select_one('a[href*="/product/"]')
            item['url'] = urljoin(base_url, link['href']) if link else 'N/A'
            item['category'] = category
            # تصویر
            img = product.select_one('img')
            item['image_url'] = img['src'] if img and img.get('src') else 'N/A'
            return item
        except Exception as e:
            logger.error(f"خطا در پارس محصول: {str(e)}")
            return None
            
    def parse_product_page(self, response: Response) -> None:
        """پارس کردن صفحه محصول برای اطلاعات اضافی"""
        try:
            item = response.meta['item']
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # استخراج توضیحات
            description = soup.select_one('div.c-product__description')
            item['description'] = description.text.strip() if description else 'N/A'
            
            # استخراج امتیاز و تعداد نظرات
            rating = soup.select_one('span.c-product__rating-score')
            item['rating'] = float(rating.text.strip()) if rating else 0.0
            
            review_count = soup.select_one('span.c-product__review-count')
            item['review_count'] = self.parse_review_count(review_count.text.strip()) if review_count else 0
            
            # استخراج مشخصات فنی
            specs = self.parse_specifications(soup)
            item['specs'] = json.dumps(specs, ensure_ascii=False)
            
            # ذخیره در پایگاه داده
            self.save_to_db(item)
            
            # استخراج نظرات کاربران
            yield from self.parse_reviews(soup, item)
            
            logger.info(f"محصول پردازش شد: {item['name']} (URL: {item['url']})")
            yield item
        except Exception as e:
            logger.error(f"خطا در پارس صفحه محصول {response.url}: {str(e)}")
            self.failed_urls.append(response.url)
            
    def parse_price(self, price_text: str) -> float:
        """پارس کردن قیمت به عدد اعشاری"""
        try:
            price = re.sub(r'[^\d]', '', price_text)
            return float(price) / 10 if price else 0.0
        except ValueError:
            return 0.0
            
    def parse_review_count(self, review_text: str) -> int:
        """پارس کردن تعداد نظرات"""
        try:
            return int(re.sub(r'[^\d]', '', review_text))
        except ValueError:
            return 0
            
    def get_image_url(self, product) -> str:
        """استخراج URL تصویر محصول"""
        try:
            img = product.select_one('img.c-product-box__img')
            return img['src'] if img and img['src'] else 'N/A'
        except Exception:
            return 'N/A'
            
    def parse_specifications(self, soup: BeautifulSoup) -> Dict:
        """استخراج مشخصات فنی محصول"""
        specs = {}
        try:
            spec_table = soup.select('div.c-product__specifications tr')
            for row in spec_table:
                key = row.select_one('th').text.strip()
                value = row.select_one('td').text.strip()
                specs[key] = value
        except Exception as e:
            logger.error(f"خطا در پارس مشخصات فنی: {str(e)}")
        return specs
        
    def parse_reviews(self, soup: BeautifulSoup, item: Dict) -> List[Dict]:
        """استخراج نظرات کاربران و ذخیره در دیتابیس"""
        try:
            reviews = soup.select('div.c-comment__item')
            for review in reviews:
                review_item = {
                    'product_url': item['url'],
                    'comment': review.select_one('p.c-comment__text').text.strip() if review.select_one('p.c-comment__text') else 'N/A',
                    'rating': float(review.select_one('span.c-comment__rating').text.strip()) if review.select_one('span.c-comment__rating') else 0.0,
                    'date': review.select_one('span.c-comment__date').text.strip() if review.select_one('span.c-comment__date') else 'N/A'
                }
                # ذخیره در دیتابیس
                self.save_review_to_db(review_item)
                yield review_item
        except Exception as e:
            logger.error(f"خطا در پارس نظرات: {str(e)}")
            
    def save_to_db(self, item: Dict) -> None:
        """ذخیره محصول در پایگاه داده"""
        try:
            product = Product(
                name=item['name'],
                price=item['price'],
                category=item['category'],
                url=item['url'],
                description=item['description'],
                rating=item['rating'],
                review_count=item['review_count'],
                image_url=item['image_url'],
                specs=item['specs']
            )
            self.session.add(product)
            self.session.commit()
            logger.info(f"محصول ذخیره شد در دیتابیس: {item['name']}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"خطا در ذخیره محصول در دیتابیس: {str(e)}")

    def save_review_to_db(self, review_item: Dict) -> None:
        """ذخیره نظر کاربر در پایگاه داده"""
        try:
            review = Review(
                product_url=review_item['product_url'],
                comment=review_item['comment'],
                rating=review_item['rating'],
                date=review_item['date']
            )
            self.session.add(review)
            self.session.commit()
            logger.info(f"نظر ذخیره شد در دیتابیس برای محصول: {review_item['product_url']}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"خطا در ذخیره نظر در دیتابیس: {str(e)}")
            
    def closed(self, reason: str) -> None:
        """اجرای عملیات پایانی"""
        elapsed_time = time.time() - self.start_time
        logger.info(f"خزیدن به پایان رسید. دلیل: {reason}")
        logger.info(f"تعداد محصولات خزیده شده: {self.items_scraped}")
        logger.info(f"زمان کل: {elapsed_time:.2f} ثانیه")
        logger.info(f"تعداد خطاها: {len(self.failed_urls)}")
        
        # ذخیره خطاها در فایل
        if self.failed_urls:
            with open('failed_urls.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.failed_urls))
        
        self.session.close()
        self.generate_report()
        self.export_structured_json()
        self.export_csv()
        
    def generate_report(self) -> None:
        """تولید گزارش آماری و تحلیل هوشمند"""
        try:
            total_items = self.items_scraped
            categories = list(self.categories_scraped)
            failed_count = len(self.failed_urls)
            execution_time = time.time() - self.start_time
            timestamp = datetime.now().isoformat()
            # تحلیل آماری محصولات
            products = self.session.query(Product).all()
            prices = [p.price for p in products if p.price > 0]
            ratings = [p.rating for p in products if p.rating > 0]
            avg_price = sum(prices) / len(prices) if prices else 0
            max_price = max(prices) if prices else 0
            min_price = min(prices) if prices else 0
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            max_rating = max(ratings) if ratings else 0
            min_rating = min(ratings) if ratings else 0
            # سیستم هشدار
            warnings = []
            if total_items < 100:
                warnings.append('تعداد محصولات بسیار کم است!')
            if failed_count > 50:
                warnings.append('تعداد خطاها زیاد است!')
            report = {
                'total_items': total_items,
                'categories': categories,
                'failed_urls': failed_count,
                'execution_time': execution_time,
                'timestamp': timestamp,
                'avg_price': avg_price,
                'max_price': max_price,
                'min_price': min_price,
                'avg_rating': avg_rating,
                'max_rating': max_rating,
                'min_rating': min_rating,
                'warnings': warnings
            }
            with open('crawler_report.json', 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=4)
            logger.info("گزارش آماری و تحلیلی تولید شد: crawler_report.json")
            if warnings:
                logger.warning(f"هشدارها: {' | '.join(warnings)}")
        except Exception as e:
            logger.error(f"خطا در تولید گزارش: {str(e)}")

    def export_structured_json(self):
        """خروجی JSON ساختارمند: محصولات و نظرات هر محصول به صورت تو در تو"""
        try:
            products = self.session.query(Product).all()
            reviews = self.session.query(Review).all()
            reviews_by_url = {}
            for r in reviews:
                reviews_by_url.setdefault(r.product_url, []).append({
                    'comment': r.comment,
                    'rating': r.rating,
                    'date': r.date
                })
            data = []
            for p in products:
                item = {
                    'name': p.name,
                    'price': p.price,
                    'category': p.category,
                    'url': p.url,
                    'description': p.description,
                    'rating': p.rating,
                    'review_count': p.review_count,
                    'image_url': p.image_url,
                    'specs': json.loads(p.specs) if p.specs else {},
                    'created_at': p.created_at.isoformat() if p.created_at else None,
                    'reviews': reviews_by_url.get(p.url, [])
                }
                data.append(item)
            with open('digikala_products_structured.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info("خروجی JSON ساختارمند تولید شد: digikala_products_structured.json")
        except Exception as e:
            logger.error(f"خطا در تولید خروجی JSON ساختارمند: {str(e)}")

    def export_csv(self):
        """خروجی CSV برای محصولات و نظرات"""
        import csv
        try:
            # محصولات
            products = self.session.query(Product).all()
            with open('digikala_products.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'price', 'category', 'url', 'description', 'rating', 'review_count', 'image_url', 'created_at'])
                for p in products:
                    writer.writerow([
                        p.name, p.price, p.category, p.url, p.description, p.rating, p.review_count, p.image_url, p.created_at.isoformat() if p.created_at else ''
                    ])
            # نظرات
            reviews = self.session.query(Review).all()
            with open('digikala_reviews.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['product_url', 'comment', 'rating', 'date', 'created_at'])
                for r in reviews:
                    writer.writerow([
                        r.product_url, r.comment, r.rating, r.date, r.created_at.isoformat() if r.created_at else ''
                    ])
            logger.info("خروجی CSV تولید شد: digikala_products.csv و digikala_reviews.csv")
        except Exception as e:
            logger.error(f"خطا در تولید خروجی CSV: {str(e)}")

def run_spider():
    """تابع برای اجرای خزنده به صورت مستقل"""
    from scrapy.crawler import CrawlerProcess
    process = CrawlerProcess()
    process.crawl(DigikalaSpider)
    process.start()

if __name__ == '__main__':
    run_spider()

# مستندات پروژه
"""
# پروژه خزنده وب دیجی‌کالا

## معرفی
این پروژه یک خزنده وب حرفه‌ای برای استخراج داده‌ها از سایت دیجی‌کالا است که اطلاعات محصولات شامل نام، قیمت، دسته‌بندی، توضیحات، امتیاز، تعداد نظرات، تصاویر، و مشخصات فنی را جمع‌آوری می‌کند.

## ویژگی‌ها
- **پشتیبانی از robots.txt**: رعایت سیاست‌های سایت.
- **ذخیره‌سازی دوگانه**: ذخیره داده‌ها در فایل JSON و پایگاه داده SQLite.
- **مدیریت خطاها**: لاگینگ پیشرفته و ذخیره URLهای ناموفق.
- **چندنخی**: استفاده از Scrapy برای مدیریت درخواست‌های همزمان.
- **گزارش‌گیری**: تولید گزارش آماری و تحلیلی از فرآیند خزیدن.
- **استخراج پیشرفته**: استخراج نظرات کاربران و مشخصات فنی.
- **خروجی ساختارمند**: خروجی JSON تو در تو و CSV برای محصولات و نظرات.
- **resume و ادامه از خطاها**: قابلیت ادامه خزیدن از URLهای ناموفق قبلی.
- **انتخاب دسته‌بندی خاص**: امکان خزیدن فقط یک دسته‌بندی خاص با پارامتر ورودی.
- **تحلیل هوشمند**: میانگین قیمت، امتیاز و هشدارهای هوشمند در گزارش.

## پیش‌نیازها
```bash
pip install scrapy beautifulsoup4 sqlalchemy
```

## نحوه اجرا
1. فایل را ذخیره کنید.
2. اجرای معمول:
```bash
scrapy runspider digikala_crawler.py
```
3. اجرای فقط یک دسته‌بندی خاص:
```bash
scrapy runspider digikala_crawler.py -a category_url=https://www.digikala.com/search/category-mobile-phone/
```
4. ادامه خزیدن از URLهای ناموفق قبلی:
```bash
scrapy runspider digikala_crawler.py -a resume_failed=True
```

## خروجی‌ها
- **digikala_products.json**: داده‌های محصولات در فرمت JSON (ساده).
- **digikala_products_structured.json**: داده‌های محصولات و نظرات به صورت تو در تو.
- **digikala_products.csv**: محصولات به صورت CSV.
- **digikala_reviews.csv**: نظرات کاربران به صورت CSV.
- **digikala.db**: پایگاه داده SQLite حاوی محصولات و نظرات.
- **crawler_report.json**: گزارش آماری و تحلیلی.
- **failed_urls.txt**: لیست URLهای ناموفق.
- **digikala_crawler.log**: لاگ اجرای برنامه.

## نکات
- حداکثر تعداد محصولات قابل تنظیم است (پیش‌فرض: 5000).
- تاخیر 3 ثانیه‌ای برای جلوگیری از مسدود شدن IP تنظیم شده است.
- قبل از خزیدن، فایل robots.txt سایت را بررسی کنید.
- برای استفاده تجاری، با دیجی‌کالا هماهنگی کنید.

## ساختار پایگاه داده
- جدول `products`:
  - id: شناسه یکتا
  - name: نام محصول
  - price: قیمت (ریال)
  - category: دسته‌بندی
  - url: آدرس محصول
  - description: توضیحات
  - rating: امتیاز
  - review_count: تعداد نظرات
  - image_url: آدرس تصویر
  - specs: مشخصات فنی (JSON)
  - created_at: زمان ثبت
- جدول `reviews`:
  - id: شناسه یکتا
  - product_url: آدرس محصول
  - comment: متن نظر
  - rating: امتیاز نظر
  - date: تاریخ نظر
  - created_at: زمان ثبت
"""