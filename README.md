
```markdown
# 🧹 Image Metadata Cleaner

**ابزار قدرتمند و امن برای حذف کامل متادیتای حساس از تصاویر**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

یک ابزار سبک، سریع و کاملاً ایرانی برای پاک‌سازی متادیتا (EXIF، GPS، مدل دوربین، تاریخ، اطلاعات حساس و ...) از عکس‌های شما.

### ✨ ویژگی‌های اصلی

- **حذف ۱۰۰٪ متادیتا** (EXIF + GPS + اطلاعات پنهان)
- پشتیبانی کامل از **JPG, PNG, WebP**
- **Batch Processing** — پردازش همزمان صدها فایل
- قابلیت **Resize** و **Watermark**
- رابط خط فرمان (CLI) بسیار ساده
- API وب (Flask) برای استفاده در پروژه‌ها و بات‌ها
- پشتیبانی از Docker
- گزارش دقیق از متادیتای حذف‌شده

### 🚀 نحوه استفاده سریع

```bash
# نصب
pip install -r requirements.txt

# پاک‌سازی تک فایل
python -m cli.main photo.jpg -o clean_photo.jpg

# پردازش گروهی + واترمارک
python -m cli.main "photos/*.jpg" -o cleaned/ --watermark "© MyBrand" --resize 1200x800
```

### 📥 نصب و اجرا

```bash
git clone https://github.com/YOUR_USERNAME/image-metadata-cleaner.git
cd image-metadata-cleaner
pip install -r requirements.txt
```

---

### ⭐️ حمایت از پروژه

اگر این ابزار براتون مفید بود، لطفاً:
- **ستاره (Star)** پروژه رو بزنید
- پروژه رو برای دوستانتون به اشتراک بگذارید

### 📢 ارتباط با ما

- **تلگرام**: [t.me/a_c_official](https://t.me/a_c_official)
- **گیت‌هاب**: [github.com/Alvandcode](https://github.com/Alvandcode)

---

**تهیه شده با ❤️ برای جامعه ایرانی**
