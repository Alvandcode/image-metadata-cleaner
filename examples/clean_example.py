from cleaner.exif_cleaner import clean_metadata, batch_clean

# مثال ساده پاک‌سازی تک فایل
result = clean_metadata("test.jpg", "test_cleaned.jpg")
print(result)

# مثال Batch
# results = batch_clean(["1.jpg", "2.jpg"], output_dir="cleaned")
# print(results)
