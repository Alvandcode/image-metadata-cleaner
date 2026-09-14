# Image Metadata Cleaner

[![Stars](https://img.shields.io/github/stars/Alvandcode/image-metadata-cleaner?style=flat-square)](https://github.com/Alvandcode/image-metadata-cleaner/stargazers) [![License](https://img.shields.io/github/license/Alvandcode/image-metadata-cleaner?style=flat-square)](./LICENSE) [![Last commit](https://img.shields.io/github/last-commit/Alvandcode/image-metadata-cleaner?style=flat-square)](https://github.com/Alvandcode/image-metadata-cleaner/commits)

> Remove EXIF and GPS metadata from images — privacy-first cleaner with batch mode, watermark and Flask API.

<div dir="rtl">

## پاک‌کننده متادیتای عکس

ابزار حفظ حریم خصوصی برای حذف کامل متادیتای EXIF و موقعیت GPS از عکس‌ها؛ با پردازش گروهی، واترمارک و API تحت وب.

</div>

---

# 🧹 Image Metadata Cleaner

**ابزار قدرتمند و امن برای حذف کامل متادیتای حساس از تصاویر**

یک ابزار سبک، سریع و کاملاً ایرانی برای پاک‌سازی متادیتا (EXIF، GPS، مدل دوربین، تاریخ، اطلاعات حساس و ...) از عکس‌های شما.

---

## ✨ ویژگی‌ها

- حذف کامل متادیتا (EXIF + GPS + ICC + XMP + کامنت‌ها) — فایل ورودی هرگز تغییر نمی‌کند
- پشتیبانی از **JPG, PNG, WebP**
- **Batch Processing** — پردازش همزمان صدها فایل
- قابلیت **Resize** و **Watermark** (مقیاس‌پذیر با اندازه عکس)
- رابط خط فرمان (CLI) ساده و قدرتمند
- API وب (Flask) امن برای استفاده در پروژه‌ها و بات‌ها (سقف حجم، اعتبارسنجی تصویر واقعی، rate-limit، هدرهای امنیتی)
- پشتیبانی از Docker (کاربر غیرروت + Healthcheck + ایمیج پین‌شده)
- گزارش دقیق از متادیتای حذف‌شده

> ⚠️ محدودیت مهم: این ابزار **متادیتا** را حذف می‌کند، نه **استگانوگرافی / واترمارک نامرئی / اثر LSB** را.
> در خروجی PNG پیکسل‌ها دقیق بازسازی می‌شوند پس داده مخفی داخل پیکسل ممکن است بماند.
> برای محو استگانوگرافی از ری‌سایز/فشرده‌سازی مجدد تهاجمی استفاده کنید.

---

## 📦 نصب

### روش ۱: نصب مستقیم (توصیه‌شده)

```bash
git clone https://github.com/Alvandcode/image-metadata-cleaner.git
cd image-metadata-cleaner
pip install -r requirements.txt
```

### روش ۲: نصب به عنوان پکیج

```bash
pip install -e .
img-clean --help
```

---

## 🚀 نحوه استفاده

### ۱. CLI (خط فرمان)

```bash
# پاک‌سازی یک فایل
python -m cli.main input.jpg -o output_clean.jpg

# پردازش گروهی
python -m cli.main "photos/*.jpg" -o cleaned/

# فقط نمایش متادیتا (بدون تغییر فایل)
python -m cli.main photo.jpg --analyze

# با امکانات پیشرفته
python -m cli.main photo.jpg \
  --resize 1200x800 \
  --watermark "© AlvandCode" \
  --quality 90 --overwrite
```

### ۲. API

```bash
python -m api.server
# یا با متغیر محیطی:
# HOST=0.0.0.0 PORT=5000 python -m api.server
```

```bash
# پاک‌سازی از طریق API
curl -X POST -F "image=@photo.jpg" http://localhost:5000/clean --output cleaned.jpg

# تحلیل متادیتا
curl -X POST -F "image=@photo.jpg" http://localhost:5000/analyze

# سلامت سرویس
curl http://localhost:5000/health
```

محدودیت‌ها: حداکثر حجم آپلود ۱۶ مگابایت (قابل تنظیم با `MAX_UPLOAD_MB`، محدوده ۱ تا ۶۴)، فقط jpg/png/webp. سقف ابعاد ~۵۰ مگاپیکسل و rate-limit پیش‌فرض ۳۰ درخواست/دقیقه/IP (قابل تنظیم با `RATE_LIMIT_PER_MIN`).

### ۳. Docker

```bash
docker build -t metadata-cleaner .
# CLI:
docker run --rm -v "$(pwd):/app" metadata-cleaner python -m cli.main photo.jpg -o clean.jpg
# API:
docker run --rm -p 5000:5000 metadata-cleaner python -m api.server
```

---

## 📋 گزینه‌های CLI

| گزینه          | توضیح                          | مثال                   |
|---------------|--------------------------------|------------------------|
| `-o, --output`| فایل خروجی یا پوشه (batch)     | `-o cleaned/`          |
| `--analyze`   | فقط نمایش متادیتا              | `--analyze`            |
| `--resize`    | تغییر اندازه                   | `--resize 800x600`     |
| `--watermark` | اضافه کردن واترمارک            | `--watermark "© Name"` |
| `--quality`   | کیفیت JPEG/WebP (۱ تا ۱۰۰)     | `--quality 90`         |
| `--overwrite` | بازنویسی خروجی موجود           | `--overwrite`          |
| `-q, --quiet` | خروجی حداقلی                   | `-q`                   |

---

## 🔒 امنیت

- فایل ورودی هرگز تغییر نمی‌کند؛ خروجی همیشه یک فایل جدید با پیکسل‌های بازسازی‌شده است. بازنویسی فایل ورودی (حتی از طریق سیم‌لینک/هاردلینک) مردود است.
- API دارای سقف حجم (۱ تا ۶۴ مگ)، اعتبارسنجی نوع واقعی تصویر، `secure_filename`، سقف ۵۰ مگاپیکسل ضد Decompression-Bomb، rate-limit و هدرهای امنیتی (`nosniff`, `DENY`, `CSP`, `HSTS`, `Permissions-Policy`) است.
- حالت `debug` فلاسک به‌صورت پیش‌فرض خاموش است و خطاهای داخلی لو نمی‌روند.
- گزارش آسیب‌پذیری: به‌جای ایشوی عمومی، از طریق تلگرام یا GitHub Security Advisory اطلاع دهید (جزئیات در `SECURITY.md`).

---

## ⭐️ حمایت از پروژه

اگر این ابزار برای شما مفید بود، لطفاً:

- **ستاره (Star)** پروژه را بزنید
- آن را برای دوستان و همکاران خود به اشتراک بگذارید

## 📢 ارتباط با ما

- **تلگرام**: [t.me/a_c_official](https://t.me/a_c_official)
- **گیت‌هاب**: [github.com/Alvandcode](https://github.com/Alvandcode)

---

**تهیه شده با ❤️ برای جامعه ایرانی**

---

## Contributing / مشارکت

- EN: Issues and Pull Requests are welcome. Please see `CONTRIBUTING.md`.
- FA: برای گزارش مشکل یا پیشنهاد قابلیت جدید، لطفا ایشو یا پول‌ریکوئست ثبت کنید.

## License / لایسنس

MIT — see [LICENSE](./LICENSE).

## Contact / ارتباط

- Telegram: https://t.me/a_c_official
- Website: https://alvandcode.github.io
