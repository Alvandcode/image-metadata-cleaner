from PIL import Image, ImageDraw, ImageFont
import piexif
import os
from typing import Dict, Optional, Tuple, List

def analyze_metadata(image_path: str) -> Dict:
    """تحلیل و نمایش متادیتای موجود در تصویر"""
    try:
        img = Image.open(image_path)
        info = {}
        
        # بررسی EXIF
        if hasattr(img, '_getexif') and img._getexif():
            exif = img._getexif()
            info['exif'] = {}
            for tag, value in exif.items():
                tag_name = piexif.TAGS.get(tag, f'Unknown_{tag}')
                info['exif'][tag_name] = str(value)[:100]
        
        # سایر متادیتا
        if img.info:
            for key, value in img.info.items():
                if key.lower() not in ['exif']:
                    info[key] = str(value)[:100]
        
        return {
            "has_metadata": len(info) > 0,
            "details": info,
            "format": img.format,
            "size": img.size,
            "mode": img.mode
        }
    except Exception as e:
        return {"error": str(e)}


def add_watermark(img: Image.Image, text: str, opacity: float = 0.3) -> Image.Image:
    """اضافه کردن واترمارک در گوشه پایین راست"""
    watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = img.width - text_width - 30
    y = img.height - text_height - 30
    
    draw.text((x, y), text, fill=(255, 255, 255, int(255 * opacity)), font=font)
    
    return Image.alpha_composite(img.convert('RGBA'), watermark)


def clean_metadata(
    input_path: str, 
    output_path: str = None,
    resize: Optional[Tuple[int, int]] = None,
    watermark_text: Optional[str] = None
) -> Dict:
    """پاک‌سازی متادیتا + امکانات اضافی"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"فایل یافت نشد: {input_path}")
    
    analysis = analyze_metadata(input_path)
    
    img = Image.open(input_path)
    
    # ایجاد تصویر تمیز
    if img.mode in ('RGBA', 'LA', 'P'):
        clean_img = Image.new(img.mode, img.size, (0, 0, 0, 0) if 'A' in img.mode else 0)
        clean_img.paste(img, (0, 0))
    else:
        clean_img = img.copy()
    
    clean_img.info.clear()
    
    # تغییر اندازه
    if resize:
        clean_img = clean_img.resize(resize, Image.Resampling.LANCZOS)
    
    # واترمارک
    if watermark_text:
        clean_img = add_watermark(clean_img, watermark_text)
    
    # پاک‌سازی اضافی برای JPEG
    if img.format == 'JPEG':
        try:
            piexif.remove(input_path)
        except:
            pass
    
    # مسیر خروجی
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_cleaned{ext}"
    
    # ذخیره
    if img.format == 'JPEG':
        clean_img = clean_img.convert('RGB')
        clean_img.save(output_path, "JPEG", quality=95, optimize=True)
    elif img.format == 'PNG':
        clean_img.save(output_path, "PNG", optimize=True)
    elif img.format == 'WEBP':
        clean_img.save(output_path, "WEBP", quality=90)
    else:
        clean_img.save(output_path)
    
    return {
        "input": input_path,
        "output": output_path,
        "status": "success",
        "original_metadata": analysis,
        "removed": list(analysis.get("details", {}).keys()),
        "resized": resize is not None,
        "watermarked": watermark_text is not None
    }


def batch_clean(input_paths: List[str], output_dir: str = None, resize=None, watermark_text=None):
    """پردازش گروهی فایل‌ها"""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    results = []
    for path in input_paths:
        try:
            if output_dir:
                name = os.path.basename(path)
                base, ext = os.path.splitext(name)
                out_path = os.path.join(output_dir, f"{base}_cleaned{ext}")
            else:
                out_path = None
            result = clean_metadata(path, out_path, resize, watermark_text)
            results.append(result)
        except Exception as e:
            results.append({"input": path, "status": "failed", "error": str(e)})
    return results
