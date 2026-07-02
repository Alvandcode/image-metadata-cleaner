
```markdown
# 🧹 Image Metadata Cleaner

**ابزار قدرتمند و امن برای حذف کامل متادیتای حساس از تصاویر**


یک ابزار سبک، سریع و کاملاً ایرانی برای پاک‌سازی متادیتا (EXIF، GPS، مدل دوربین، تاریخ، اطلاعات حساس و ...) از عکس‌های شما.

---

## ✨ ویژگی‌ها

- حذف ۱۰۰٪ متادیتا (EXIF + GPS + اطلاعات پنهان)
- پشتیبانی کامل از **JPG, PNG, WebP**
- **Batch Processing** — پردازش همزمان صدها فایل
- قابلیت **Resize** و **Watermark**
- رابط خط فرمان (CLI) بسیار ساده و قدرتمند
- API وب (Flask) برای استفاده در پروژه‌ها و بات‌ها
- پشتیبانی از Docker
- گزارش دقیق از متادیتای حذف‌شده

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
```

---

## 🚀 نحوه استفاده

### ۱. CLI (خط فرمان)

```bash
# پاک‌سازی یک فایل
python -m cli.main input.jpg -o output_clean.jpg

# پردازش گروهی
python -m cli.main "photos/*.jpg" -o cleaned/

# با امکانات پیشرفته
python -m cli.main photo.jpg \
  --resize 1200x800 \
  --watermark "© AlvandCode"
```

### ۲. API

```bash
python -m api.server
```

```bash
# پاک‌سازی از طریق API
curl -X POST -F "image=@photo.jpg" http://localhost:5000/clean --output cleaned.jpg
```

### ۳. Docker

```bash
docker build -t metadata-cleaner .
docker run --rm -v $(pwd):/app metadata-cleaner python -m cli.main photo.jpg -o clean.jpg
```

---

## 📋 گزینه‌های CLI

| گزینه           | توضیح                          | مثال                     |
|------------------|--------------------------------|--------------------------|
| `--analyze`      | نمایش متادیتا                 | `--analyze`              |
| `--resize`       | تغییر اندازه                   | `--resize 800x600`       |
| `--watermark`    | اضافه کردن واترمارک          | `--watermark "© Name"`   |

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
