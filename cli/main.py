import argparse
import sys
import glob
import os
from cleaner.exif_cleaner import clean_metadata, analyze_metadata, batch_clean

def main():
    parser = argparse.ArgumentParser(
        description="🧹 Image Metadata Cleaner - حذف متادیتای حساس از عکس‌ها",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("input", help="مسیر فایل یا الگو (مثال: *.jpg)")
    parser.add_argument("-o", "--output", help="مسیر خروجی یا پوشه")
    parser.add_argument("--analyze", action="store_true", help="فقط نمایش متادیتا")
    parser.add_argument("--resize", help="تغییر اندازه - مثال: 800x600")
    parser.add_argument("--watermark", help="متن واترمارک")
    
    args = parser.parse_args()
    
    # پشتیبانی از الگو (wildcard)
    inputs = glob.glob(args.input) if '*' in args.input or '?' in args.input else [args.input]
    
    try:
        if args.analyze:
            for inp in inputs:
                if os.path.exists(inp):
                    result = analyze_metadata(inp)
                    print(f"\n📊 تحلیل {inp}:")
                    import json
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        
        # تبدیل resize
        resize = None
        if args.resize:
            try:
                w, h = map(int, args.resize.split('x'))
                resize = (w, h)
            except:
                print("❌ فرمت resize اشتباه است. مثال: 800x600")
                sys.exit(1)
        
        # تشخیص حالت Batch یا تک فایل
        if len(inputs) > 1 or (args.output and os.path.isdir(args.output)) or '*' in args.input:
            results = batch_clean(inputs, args.output, resize, args.watermark)
            success = sum(1 for r in results if r.get("status") == "success")
            print(f"✅ پردازش گروهی تمام شد! {success}/{len(results)} فایل موفق")
        else:
            result = clean_metadata(inputs[0], args.output, resize, args.watermark)
            print("✅ پاک‌سازی با موفقیت انجام شد!")
            print(f"ورودی: {result['input']}")
            print(f"خروجی: {result['output']}")
            if result.get("resized"):
                print("📏 تغییر اندازه اعمال شد")
            if result.get("watermarked"):
                print("🔖 واترمارک اضافه شد")
                
    except Exception as e:
        print(f"❌ خطا: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
