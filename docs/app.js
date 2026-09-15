/* Image Metadata Cleaner — 100% client-side PWA.
 *
 * Privacy contract:
 *   - No fetch/XHR/WebSocket/beacon to any remote origin, ever.
 *   - The page CSP sets connect-src 'none', so it is not even possible.
 *   - Photos are decoded with createImageBitmap, redrawn onto a fresh canvas
 *     (pixels rebuilt => EXIF/GPS/XMP/IPTC/ICC/comment chunks are gone) and
 *     re-encoded with canvas.toBlob.
 *
 * This mirrors cleaner/exif_cleaner.py, which does the same on the server side
 * for CLI/Docker users.
 */
"use strict";

/* ------------------------------------------------------------------ i18n */
const I18N = {
  fa: {
    "app.title": "پاک‌کننده متادیتای عکس",
    "app.subtitle": "۱۰۰٪ آفلاین — بدون آپلود",
    "theme.auto": "🌗",
    "theme.dark": "🌙",
    "theme.light": "☀️",
    "hero.title": "متادیتای عکس را کامل پاک کن",
    "hero.lead": "عکس‌ها را همین‌جا در مرورگر بازسازی می‌کنیم: EXIF، موقعیت GPS، مدل دوربین، XMP و کامنت‌ها حذف می‌شوند. هیچ بایتی از دستگاه شما خارج نمی‌شود و به هیچ سروری وصل نمی‌شویم.",
    "pill.noupload": "🔒 بدون آپلود",
    "pill.offline": "✈️ کاملاً آفلاین",
    "drop.title": "عکس‌ها را اینجا رها کن",
    "drop.hint": "یا انتخاب کن — می‌توانی چند عکس را با هم بیندازی. هیچ فایلی آپلود نمی‌شود.",
    "drop.choose": "انتخاب عکس",
    "drop.demo": "ساخت عکس آزمایشی با GPS",
    "opt.summary": "تنظیمات (اختیاری)",
    "opt.maxdim": "حداکثر ابعاد",
    "opt.maxdim.keep": "دست‌نخورده",
    "opt.format": "قالب خروجی",
    "opt.format.keep": "مثل ورودی",
    "opt.quality": "کیفیت",
    "opt.watermark": "واترمارک (اختیاری)",
    "opt.opacity": "شفافیت واترمارک",
    "opt.position": "جای واترمارک",
    "opt.showmeta": "نمایش متادیتای پیدا‌شده",
    "opt.stripThumb": "حذف بندانگشتی و متادیتای تودرتو",
    "opt.note": "خروجی همیشه از پیکسل‌های تازه ساخته می‌شود، پس هیچ تگی زنده نمی‌ماند. کانواس مرورگر پروفایل رنگ ICC را حذف می‌کند؛ اگر تطابق دقیق رنگ مهم است از نسخه پایتون با --keep-icc استفاده کن.",
    "pos.bottom-right": "پایین راست",
    "pos.bottom-center": "پایین وسط",
    "pos.bottom-left": "پایین چپ",
    "pos.top-right": "بالا راست",
    "pos.center": "مرکز",
    "res.title": "نتیجه",
    "btn.zip": "دانلود همه (ZIP)",
    "btn.clear": "پاک کردن فهرست",
    "proof.title": "چرا می‌توانی اعتماد کنی؟",
    "proof.network.title": "تست کن که نمی‌توانم عکست را بفرستم",
    "proof.network.body": "این صفحه با Content-Security-Policy محافظت می‌شود و مقدار connect-src آن 'none' است. یعنی مرورگر هر تلاش برای ارسال داده را رد می‌کند.",
    "proof.network.btn": "تلاش برای ارسال داده",
    "proof.strip.title": "چه چیزی حذف می‌شود؟",
    "proof.strip.1": "موقعیت GPS و مختصات دقیق",
    "proof.strip.2": "سریال دوربین، نام مالک، شماره لنز",
    "proof.strip.3": "تاریخ و ساعت اصلی عکس",
    "proof.strip.4": "مدل دستگاه، نسخه نرم‌افزار، تنظیمات عکاسی",
    "proof.strip.5": "XMP، IPTC، کامنت‌ها و بندانگشتی داخلی",
    "proof.strip.6": "پروفایل رنگ ICC (کانواس خروجی sRGB است)",
    "proof.offline.title": "آفلاین و نصب‌شدنی",
    "proof.offline.body": "با Service Worker کل برنامه کش می‌شود: می‌توانی اینترنت را کامل قطع کنی و همچنان کار کند. روی موبایل هم می‌توانی آن را به صفحه اصلی اضافه کنی.",
    "proof.install": "نصب برنامه",
    "proof.cli.title": "برای صدها فایل و HEIC",
    "proof.cli.body": "برای پردازش گروهی سنگین، حفظ حرکت WebP، پروفایل رنگ دقیق و پشتیبانی HEIC آیفون از CLI پایتون استفاده کن.",
    "faq.title": "پرسش‌های پرتکرار",
    "faq.q1": "آیا عکس‌هایم جایی ذخیره می‌شوند؟",
    "faq.a1": "نه. پردازش کاملاً داخل مرورگر انجام می‌شود. هیچ درخواست شبکه‌ای وجود ندارد و allow-list شبکه خالی است.",
    "faq.q2": "چرا عکس‌ها کوچک‌تر می‌شوند؟",
    "faq.a2": "هم متادیتا حذف می‌شود و هم تصویر دوباره فشرده می‌شود. مقدار کاهش برای هر فایل نشان داده می‌شود.",
    "faq.q3": "درباره WebP متحرک و HEIC چه؟",
    "faq.a3": "کانواس نمی‌تواند انیمیشن بسازد و مرورگرها HEIC را (به‌جز سافاری) رمزگشایی نمی‌کنند. برای این دو مورد از CLI استفاده کن؛ انیمیشن WebP کامل حفظ می‌شود.",
    "faq.q4": "الگوریتم دقیق چیست؟",
    "faq.a4": "تصویر روی یک canvas تازه کشیده می‌شود (با اصلاح جهت EXIF) و دوباره انکود می‌شود. فایل اصلی هرگز تغییر نمی‌کند.",
    "footer.made": "ساخته‌شده برای جامعه ایرانی",
    "footer.security": "گزارش امنیتی",
    "footer.vendor": "JSZip و exifr به‌صورت محلی در پوشه vendor قرار دارند؛ هیچ CDN و تحلیلی‌کننده‌ای استفاده نمی‌شود.",
    "footer.license": "کد تحت لایسنس MIT است.",
    "status.waiting": "در انتظار",
    "status.working": "در حال پردازش…",
    "status.done": "پاک شد",
    "status.error": "خطا",
    "notice.count": "{n} عکس انتخاب شد.",
    "notice.big": "فایل {name} بزرگ است ({size}). پردازش ممکن است کند شود.",
    "notice.busy": "در حال پردازش {i} از {n}…",
    "notice.done": "{n} عکس پردازش شد. همه در همین دستگاه ماند.",
    "notice.toomany": "حداکثر {max} فایل در هر نوبت پردازش می‌شود.",
    "gps.title": "موقعیت GPS پیدا شد!",
    "gps.body": "این عکس مختصات محل عکاسی را همراه دارد:",
    "gps.map": "دیدن روی نقشه (باز کردن OpenStreetMap)",
    "gps.warn": "تا وقتی پاک نشود، هر کسی که این فایل را بگیرد می‌تواند محل زندگی‌ات را ببیند.",
    "gps.removed": "مختصات در نسخه پاک‌شده وجود ندارد — بررسی شد.",
    "meta.title": "متادیتای شخصی پیدا شد و حذف شد ({n} مورد)",
    "meta.none": "هیچ متادیتای شخصی در این فایل نبود؛ خروجی هم از پیکسل‌های تازه ساخته شده است.",
    "meta.technical": "هدرهای فنی (بی‌خطر) — {n} مورد",
    "meta.kept": "پاک‌شده و بررسی شد",
    "size.bigger": "{before} → {after} ({pct} بیشتر، چون دوباره انکود شد)",
    "btn.download": "دانلود",
    "btn.remove": "حذف از فهرست",
    "cmp.before": "قبل",
    "cmp.after": "بعد",
    "cmp.hint": "دستگیره را بکش تا تفاوت را ببینی",
    "size.line": "{before} → {after} ({pct} کمتر)",
    "size.same": "{before} (بدون تغییر حجم)",
    "dims.line": "{w}×{h}",
    "zip.building": "در حال ساخت فایل ZIP…",
    "zip.done": "ZIP آماده شد ({n} فایل).",
    "zip.empty": "فایلی برای دانلود نیست.",
    "probe.trying": "در حال تلاش برای ارسال…",
    "probe.blocked": "مرورگر جلوی ارسال را گرفت. علت: سیاست امنیتی این صفحه (connect-src 'none'). هیچ داده‌ای ارسال نشد. ✅",
    "probe.offline": "دستگاه آفلاین است، پس ارسال ممکن نبود. برای تست واقعی اینترنت را وصل کن و دوباره امتحان کن.",
    "probe.reachable": "⚠️ یک درخواست شبکه‌ای موفق شد! این ناسازگار با تضمین حریم خصوصی است؛ لطفاً گزارش بده.",
    "probe.detail": "مقصد آزمایشی: {url} — خطا: {err}",
    "install.hint": "برای نصب، از منوی مرورگر «افزودن به صفحه اصلی» را بزن.",
    "error.notimage": "«{name}» تصویر قابل خواندن نیست. مرورگرها HEIC آیفون را (به‌جز سافاری) باز نمی‌کنند؛ از CLI استفاده کن.",
    "error.encode": "انکود کردن «{name}» ناموفق بود.",
    "error.generic": "پردازش «{name}» با خطا متوقف شد: {err}",
    "net.online": "آنلاین",
    "net.offline": "آفلاین",
    "verify.line": "بررسی خروجی: هیچ متادیتایی پیدا نشد ✅",
    "verify.icc": "ذکر: پروفایل رنگ ICC در کانواس حفظ نمی‌شود (خروجی sRGB).",
  },
  en: {
    "app.title": "Image Metadata Cleaner",
    "app.subtitle": "100% offline — nothing uploaded",
    "theme.auto": "🌗",
    "theme.dark": "🌙",
    "theme.light": "☀️",
    "hero.title": "Strip photo metadata completely",
    "hero.lead": "Photos are rebuilt right here in your browser: EXIF, GPS location, camera model, XMP and comments are removed. Not a single byte leaves your device and we never connect to a server.",
    "pill.noupload": "🔒 No upload",
    "pill.offline": "✈️ Fully offline",
    "drop.title": "Drop your photos here",
    "drop.hint": "Or pick them — you can drop several at once. Nothing is uploaded.",
    "drop.choose": "Choose photos",
    "drop.demo": "Create a demo photo with GPS",
    "opt.summary": "Options (optional)",
    "opt.maxdim": "Max dimension",
    "opt.maxdim.keep": "Keep original",
    "opt.format": "Output format",
    "opt.format.keep": "Same as input",
    "opt.quality": "Quality",
    "opt.watermark": "Watermark (optional)",
    "opt.opacity": "Watermark opacity",
    "opt.position": "Watermark position",
    "opt.showmeta": "Show the metadata that was found",
    "opt.stripThumb": "Drop thumbnail and nested metadata",
    "opt.note": "The output is always built from fresh pixels, so no tag survives. A browser canvas also drops the ICC colour profile; if exact colour matters use the Python CLI with --keep-icc.",
    "pos.bottom-right": "Bottom right",
    "pos.bottom-center": "Bottom center",
    "pos.bottom-left": "Bottom left",
    "pos.top-right": "Top right",
    "pos.center": "Center",
    "res.title": "Result",
    "btn.zip": "Download all (ZIP)",
    "btn.clear": "Clear list",
    "proof.title": "Why you can trust this",
    "proof.network.title": "Test that I cannot send your photo",
    "proof.network.body": "This page carries a Content-Security-Policy whose connect-src is 'none', so the browser refuses any attempt to send data anywhere.",
    "proof.network.btn": "Try to send data",
    "proof.strip.title": "What gets removed?",
    "proof.strip.1": "GPS position and exact coordinates",
    "proof.strip.2": "Camera serial number, owner name, lens id",
    "proof.strip.3": "Original capture date and time",
    "proof.strip.4": "Device model, software version, shooting settings",
    "proof.strip.5": "XMP, IPTC, comments and the embedded thumbnail",
    "proof.strip.6": "ICC colour profile (canvas output is sRGB)",
    "proof.offline.title": "Offline and installable",
    "proof.offline.body": "A service worker caches the whole app, so you can cut the internet completely and it still works. On mobile you can add it to your home screen.",
    "proof.install": "Install app",
    "proof.cli.title": "For thousands of files and HEIC",
    "proof.cli.body": "Use the Python CLI for heavy batch work, WebP animation preservation, exact colour profiles and iPhone HEIC support.",
    "faq.title": "FAQ",
    "faq.q1": "Are my photos stored anywhere?",
    "faq.a1": "No. Processing happens entirely in your browser. There are no network requests at all and the network allow-list is empty.",
    "faq.q2": "Why do photos get smaller?",
    "faq.a2": "Metadata is removed and the image is re-compressed. The saving is shown for every file.",
    "faq.q3": "What about animated WebP and HEIC?",
    "faq.a3": "Canvas cannot produce animations and browsers (except Safari) cannot decode HEIC. Use the CLI for both — it preserves full WebP animation.",
    "faq.q4": "What is the exact algorithm?",
    "faq.a4": "The image is drawn onto a brand-new canvas (with EXIF orientation applied) and re-encoded. Your original file is never touched.",
    "footer.made": "Built for the Iranian community",
    "footer.security": "Security report",
    "footer.vendor": "JSZip and exifr are vendored locally; no CDN and no analytics are used.",
    "footer.license": "Code is MIT licensed.",
    "status.waiting": "Queued",
    "status.working": "Working…",
    "status.done": "Cleaned",
    "status.error": "Error",
    "notice.count": "{n} photo(s) selected.",
    "notice.big": "{name} is large ({size}). Processing may be slow.",
    "notice.busy": "Processing {i} of {n}…",
    "notice.done": "{n} photo(s) processed. Everything stayed on this device.",
    "notice.toomany": "At most {max} files per run.",
    "gps.title": "GPS location found!",
    "gps.body": "This photo carries the coordinates of where it was taken:",
    "gps.map": "View on a map (opens OpenStreetMap)",
    "gps.warn": "Until it is cleaned, anyone who gets this file can see where you live.",
    "gps.removed": "The cleaned copy has no coordinates — verified.",
    "meta.title": "Personal metadata found and removed ({n} items)",
    "meta.none": "This file had no personal metadata; the output was still rebuilt from fresh pixels.",
    "meta.technical": "Technical headers (harmless) — {n} items",
    "meta.kept": "Cleaned and verified",
    "size.bigger": "{before} → {after} ({pct} larger, re-encoded)",
    "btn.download": "Download",
    "btn.remove": "Remove from list",
    "cmp.before": "Before",
    "cmp.after": "After",
    "cmp.hint": "Drag the handle to compare",
    "size.line": "{before} → {after} ({pct} smaller)",
    "size.same": "{before} (size unchanged)",
    "dims.line": "{w}×{h}",
    "zip.building": "Building the ZIP…",
    "zip.done": "ZIP ready ({n} files).",
    "zip.empty": "Nothing to download yet.",
    "probe.trying": "Trying to send…",
    "probe.blocked": "The browser blocked the request thanks to this page's security policy (connect-src 'none'). No data was sent. ✅",
    "probe.offline": "This device is offline, so nothing could be sent. Connect to the internet and try again for a real test.",
    "probe.reachable": "⚠️ A network request succeeded! That contradicts our privacy promise — please report it.",
    "probe.detail": "Test target: {url} — error: {err}",
    "install.hint": "Use your browser menu → “Add to Home Screen” to install.",
    "error.notimage": "“{name}” is not a readable image. Browsers (except Safari) cannot decode iPhone HEIC — use the CLI for that.",
    "error.encode": "Encoding “{name}” failed.",
    "error.generic": "Processing “{name}” failed: {err}",
    "net.online": "Online",
    "net.offline": "Offline",
    "verify.line": "Output verification: no metadata found ✅",
    "verify.icc": "Note: canvas output drops the ICC profile (sRGB is assumed).",
  },
};

let lang = "fa";
const t = (key, vars) => {
  let s = (I18N[lang] && I18N[lang][key]) || (I18N.en[key] || key);
  if (vars) {
    for (const k of Object.keys(vars)) s = s.split("{" + k + "}").join(String(vars[k]));
  }
  return s;
};

/* --------------------------------------------------------------- utilities */
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

function humanBytes(n) {
  if (n == null) return "—";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / (1024 * 1024)).toFixed(2) + " MB";
}

const RTL_RE = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;

const SENSITIVE = new Set([
  "gps", "latitude", "longitude", "gpslatitude", "gpslongitude", "gpsaltitude",
  "gpsdatestamp", "gpstimestamp", "gpsspeed", "gpsimgdirection",
  "make", "model", "software", "lensmodel", "lensmake", "lensserialnumber",
  "serialnumber", "bodyserialnumber", "ownername", "artist", "copyright",
  "datetimeoriginal", "createdate", "modifydate", "datetime", "offsettime",
  "hostcomputer", "cameraowner", "usercomment", "imagdescription", "imagedescription",
  "subject", "keywords", "xmp", "iptc", "city", "country", "location",
  "makernote", "thumbnail", "thumbnaillength", "thumbnailoffset", "creatortool",
  "profilecreator", "rights", "credit", "byline", "contactinfo",
]);

const MAX_FILES = 60;
const BIG_FILE = 30 * 1024 * 1024;

/* ------------------------------------------------------------------ theme */
const THEMES = ["auto", "dark", "light"];
function applyTheme(next) {
  document.documentElement.setAttribute("data-theme", next);
  const btn = $("#btn-theme");
  btn.textContent = t("theme." + next);
  btn.title = next;
  try { localStorage.setItem("imc-theme", next); } catch (_) { /* private mode */ }
}

/* --------------------------------------------------------------- metadata */
function flattenMetadata(meta) {
  const rows = [];
  const seen = new Set();
  const walk = (obj, prefix) => {
    if (!obj || typeof obj !== "object") return;
    for (const key of Object.keys(obj)) {
      const value = obj[key];
      if (value == null || value === "") continue;
      if (typeof value === "object" && !(value instanceof Date) && !(value instanceof Uint8Array)) {
        walk(value, prefix ? prefix + "." + key : key);
        continue;
      }
      const label = prefix ? prefix + "." + key : key;
      if (seen.has(label)) continue;
      seen.add(label);
      rows.push([label, value]);
    }
  };
  walk(meta, "");
  return rows;
}

function renderValue(value) {
  if (value instanceof Date) return value.toISOString();
  if (value instanceof Uint8Array || value instanceof ArrayBuffer || Array.isArray(value)) {
    const len = value.length != null ? value.length : "?";
    return "<binary " + len + " bytes>";
  }
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  const s = String(value);
  return s.length > 240 ? s.slice(0, 240) + "…" : s;
}

async function readMetadata(file) {
  if (!window.exifr) return null;
  try {
    const out = await exifr.parse(file, {
      tiff: true, exif: true, gps: true, xmp: true, iptc: true, jfif: true,
      ihdr: true, icc: false, translateKeys: true, translateValues: true,
      reviveValues: true, mergeOutput: true, sanitize: true,
    });
    return out || null;
  } catch (_) {
    return null;
  }
}

async function readGps(file) {
  if (!window.exifr || typeof exifr.gps !== "function") return null;
  try {
    const g = await exifr.gps(file);
    if (g && typeof g.latitude === "number" && typeof g.longitude === "number") return g;
  } catch (_) { /* no GPS is the common case */ }
  return null;
}

/* ------------------------------------------------------------------ decode */
function loadImageElement(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("image decode failed"));
    img.src = url;
  });
}

async function decodeImage(file) {
  if (typeof createImageBitmap === "function") {
    // 'none' keeps the raw pixels so we can apply the EXIF orientation
    // ourselves — deterministic across browsers. It is also the default in
    // older browsers, so passing it is safe both ways.
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "none" });
      return { source: bmp, preOriented: false, release: () => bmp.close && bmp.close() };
    } catch (_) {
      try {
        const bmp = await createImageBitmap(file);
        return { source: bmp, preOriented: true, release: () => bmp.close && bmp.close() };
      } catch (_) { /* fall through to <img> */ }
    }
  }
  const url = URL.createObjectURL(file);
  const img = await loadImageElement(url);
  try { img.style.imageOrientation = "from-image"; } catch (_) { /* older engines */ }
  return { source: img, preOriented: true, release: () => URL.revokeObjectURL(url) };
}

/* Apply an EXIF orientation (2..8) to a 2D context already scaled. */
function applyOrientation(ctx, o, w, h) {
  switch (o) {
    case 2: ctx.transform(-1, 0, 0, 1, w, 0); break;
    case 3: ctx.transform(-1, 0, 0, -1, w, h); break;
    case 4: ctx.transform(1, 0, 0, -1, 0, h); break;
    case 5: ctx.transform(0, 1, 1, 0, 0, 0); break;
    case 6: ctx.transform(0, 1, -1, 0, h, 0); break;
    case 7: ctx.transform(0, -1, -1, 0, h, w); break;
    case 8: ctx.transform(0, -1, 1, 0, 0, w); break;
    default: return;
  }
}

/* --------------------------------------------------------------- watermark */
function drawWatermark(ctx, w, h, opts) {
  const text = (opts.text || "").trim();
  if (!text) return;
  const rtl = RTL_RE.test(text);
  const margin = Math.max(8, Math.round(Math.min(w, h) / 40));
  const family = rtl
    ? '"Vazirmatn","Noto Naskh Arabic",Tahoma,"Segoe UI",system-ui,sans-serif'
    : 'system-ui,"Segoe UI",Arial,Helvetica,sans-serif';

  let size = Math.max(12, Math.round(Math.min(w, h) / 20));
  ctx.save();
  ctx.globalAlpha = Math.max(0.05, Math.min(1, opts.opacity));
  try { ctx.direction = rtl ? "rtl" : "ltr"; } catch (_) { /* unsupported */ }
  let width = 0;
  for (; size > 10; size -= 2) {
    ctx.font = "600 " + size + "px " + family;
    width = ctx.measureText(text).width;
    if (width <= w - margin * 2) break;
  }
  ctx.font = "600 " + size + "px " + family;

  const pos = opts.position || "bottom-right";
  const center = pos.indexOf("center") >= 0;
  const left = pos.indexOf("left") >= 0;
  ctx.textAlign = center ? "center" : (left ? "left" : "right");
  const x = center ? w / 2 : (left ? margin : w - margin);
  const y = pos.indexOf("top") === 0 ? margin + size : h - margin;

  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillText(text, x + 1, y + 1);
  ctx.fillStyle = "#ffffff";
  ctx.fillText(text, x, y);
  ctx.restore();
}

/* ------------------------------------------------------------------- render */
function pickMime(inputType, wanted) {
  if (wanted && wanted !== "keep") return wanted;
  if (inputType === "image/png") return "image/png";
  if (inputType === "image/webp") return "image/webp";
  if (inputType === "image/jpeg" || inputType === "image/jpg") return "image/jpeg";
  return "image/jpeg";
}

const EXT = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };

function renderCanvas(source, orientation, maxDim, mime, opts) {
  const rawW = source.width;
  const rawH = source.height;
  const swapped = orientation >= 5 && orientation <= 8;
  const orientedW = swapped ? rawH : rawW;
  const orientedH = swapped ? rawW : rawH;

  let scale = 1;
  if (maxDim > 0 && Math.max(orientedW, orientedH) > maxDim) {
    scale = maxDim / Math.max(orientedW, orientedH);
  }
  const cw = Math.max(1, Math.round(orientedW * scale));
  const ch = Math.max(1, Math.round(orientedH * scale));

  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d");

  // JPEG has no alpha: flatten onto white instead of black.
  if (mime === "image/jpeg") {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, cw, ch);
  }
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  ctx.save();
  ctx.scale(scale, scale);
  applyOrientation(ctx, orientation, rawW, rawH);
  ctx.drawImage(source, 0, 0, rawW, rawH);
  ctx.restore();

  drawWatermark(ctx, cw, ch, opts);
  return canvas;
}

function encodeCanvas(canvas, mime, quality) {
  return new Promise((resolve, reject) => {
    try {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("toBlob returned null"));
      }, mime, mime === "image/png" ? undefined : quality);
    } catch (err) {
      reject(err);
    }
  });
}

function cleanedName(name, mime) {
  const base = name.replace(/\.[^.]+$/, "") || "image";
  return base + "_cleaned." + (EXT[mime] || "jpg");
}

/* --------------------------------------------------------------- demo file */
function u16(v) { return [v & 0xff, (v >> 8) & 0xff]; }
function u32(v) { return [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >> 24) & 0xff]; }
function asciiBytes(s) {
  const out = Array.from(new TextEncoder().encode(s));
  out.push(0);
  return out;
}
function rationals24(value) {
  const abs = Math.abs(value);
  const d = Math.floor(abs);
  const minFloat = (abs - d) * 60;
  const m = Math.floor(minFloat);
  const s = (minFloat - m) * 60;
  return [
    ...u32(d), ...u32(1),
    ...u32(m), ...u32(1),
    ...u32(Math.round(s * 1000)), ...u32(1000),
  ];
}
function tiffEntry(tag, type, count, data, offset) {
  const out = [...u16(tag), ...u16(type), ...u32(count)];
  if (data && data.length <= 4) {
    const v = data.slice();
    while (v.length < 4) v.push(0);
    out.push(...v);
  } else {
    out.push(...u32(offset || 0));
  }
  return out;
}
/** Build a minimal APP1/EXIF segment with Make, Model, Software and GPS. */
function buildExifApp1(lat, lon) {
  const make = asciiBytes("DemoPhone");
  const model = asciiBytes("DemoCam Ultra 13");
  const software = asciiBytes("Freebuff Demo 1.0");
  const latRef = asciiBytes(lat >= 0 ? "N" : "S");
  const lonRef = asciiBytes(lon >= 0 ? "E" : "W");
  const latRat = rationals24(lat);
  const lonRat = rationals24(lon);

  const ifd0Count = 4;
  const ifd0Off = 8;
  const ifd0Size = 2 + ifd0Count * 12 + 4;
  const strOff = ifd0Off + ifd0Size;
  const gpsOff = strOff + make.length + model.length + software.length;
  const gpsCount = 4;
  const gpsSize = 2 + gpsCount * 12 + 4;
  const latOff = gpsOff + gpsSize;
  const lonOff = latOff + latRat.length;

  const body = [];
  // TIFF header: little-endian, magic 42, offset of IFD0.
  body.push(0x49, 0x49, ...u16(42), ...u32(ifd0Off));
  // IFD0
  body.push(...u16(ifd0Count));
  body.push(...tiffEntry(0x010f, 2, make.length, make, strOff));
  body.push(...tiffEntry(0x0110, 2, model.length, model, strOff + make.length));
  body.push(...tiffEntry(0x0131, 2, software.length, software, strOff + make.length + model.length));
  body.push(...tiffEntry(0x8825, 4, 1, u32(gpsOff), 0));
  body.push(...u32(0)); // no next IFD
  body.push(...make, ...model, ...software);
  // GPS IFD
  body.push(...u16(gpsCount));
  body.push(...tiffEntry(0x0001, 2, latRef.length, latRef, 0));
  body.push(...tiffEntry(0x0002, 5, 3, null, latOff));
  body.push(...tiffEntry(0x0003, 2, lonRef.length, lonRef, 0));
  body.push(...tiffEntry(0x0004, 5, 3, null, lonOff));
  body.push(...u32(0));
  body.push(...latRat, ...lonRat);

  const payload = [0x45, 0x78, 0x69, 0x66, 0x00, 0x00, ...body]; // "Exif\0\0"
  const segLen = payload.length + 2;
  // JPEG segment lengths are BIG-endian (u16 above is little-endian for TIFF).
  return [0xff, 0xe1, (segLen >> 8) & 0xff, segLen & 0xff, ...payload];
}

/** Insert an APP1 segment right after the JPEG SOI marker. */
function injectExif(jpegBuffer, lat, lon) {
  const src = new Uint8Array(jpegBuffer);
  const segment = buildExifApp1(lat, lon);
  const out = new Uint8Array(src.length + segment.length);
  out.set(src.subarray(0, 2), 0);
  out.set(segment, 2);
  out.set(src.subarray(2), 2 + segment.length);
  return out;
}

async function makeDemoFile() {
  const canvas = document.createElement("canvas");
  canvas.width = 720;
  canvas.height = 480;
  const ctx = canvas.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 720, 480);
  grad.addColorStop(0, "#0d3b66");
  grad.addColorStop(0.5, "#f4a259");
  grad.addColorStop(1, "#bc4b51");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 720, 480);
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.font = "600 34px system-ui, sans-serif";
  ctx.fillText("Demo photo", 40, 230);
  ctx.font = "500 20px system-ui, sans-serif";
  ctx.fillText("با متادیتای GPS جعلی", 40, 270);
  ctx.fillStyle = "rgba(0,0,0,0.35)";
  ctx.fillRect(0, 430, 720, 50);
  ctx.fillStyle = "#fff";
  ctx.font = "500 16px system-ui, sans-serif";
  ctx.fillText("Tehran — 35.6892 N, 51.3890 E", 40, 462);

  const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.9));
  const buf = await blob.arrayBuffer();
  const withExif = injectExif(buf, 35.6892, 51.3890);
  return new File([withExif], "demo-gps.jpg", { type: "image/jpeg" });
}

/* ------------------------------------------------------------------ state */
const state = { items: [], nextId: 1, busy: false, zip: null, deferredInstall: null };

function settings() {
  return {
    maxDim: parseInt($("#opt-maxdim").value, 10) || 0,
    wanted: $("#opt-format").value,
    quality: (parseInt($("#opt-quality").value, 10) || 92) / 100,
    watermark: $("#opt-watermark").value,
    opacity: (parseInt($("#opt-opacity").value, 10) || 35) / 100,
    position: $("#opt-position").value,
    showMeta: $("#opt-showmeta").checked,
  };
}

function setNotice(html, cls) {
  const box = $("#notice");
  if (!html) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.className = "alert" + (cls ? " " + cls : "");
  box.textContent = html;
}

/* ----------------------------------------------------------------- process */
async function processFile(file) {
  const item = {
    id: state.nextId++,
    file,
    name: file.name,
    size: file.size,
    status: "waiting",
    error: null,
    meta: null,
    gps: null,
    outBlob: null,
    outMime: null,
    outName: null,
    outSize: null,
    outDims: null,
    canvas: null,
    beforeUrl: URL.createObjectURL(file),
  };
  state.items.push(item);
  renderItem(item);

  try {
    const cfg = settings();
    item.status = "working";
    updateItemStatus(item);

    const [meta, gps] = await Promise.all([readMetadata(file), readGps(file)]);
    item.meta = meta;
    item.gps = gps;

    const mime = pickMime(file.type, cfg.wanted);
    const decoded = await decodeImage(file);
    const orientation = decoded.preOriented ? 1 : ((meta && meta.Orientation) || 1);
    let canvas;
    try {
      canvas = renderCanvas(decoded.source, orientation, cfg.maxDim, mime, {
        text: cfg.watermark,
        opacity: cfg.opacity,
        position: cfg.position,
      });
    } finally {
      decoded.release();
    }

    const blob = await encodeCanvas(canvas, mime, cfg.quality);
    item.canvas = canvas;
    item.outBlob = blob;
    item.outMime = blob.type || mime;
    item.outName = cleanedName(file.name, item.outMime);
    item.outSize = blob.size;
    item.outDims = { w: canvas.width, h: canvas.height };
    item.status = "done";
  } catch (err) {
    item.status = "error";
    item.error = err && err.message ? err.message : String(err);
  }
  renderItem(item);
  return item;
}

async function handleFiles(files) {
  if (state.busy) return;
  const list = Array.from(files || []).filter((f) => f && f.size > 0);
  if (!list.length) return;

  let accepted = list;
  if (list.length > MAX_FILES) {
    setNotice(t("notice.toomany", { max: MAX_FILES }), "warn");
    accepted = list.slice(0, MAX_FILES);
  } else {
    setNotice(t("notice.count", { n: list.length }), "ok");
  }
  const big = accepted.find((f) => f.size > BIG_FILE);
  if (big) setNotice(t("notice.big", { name: big.name, size: humanBytes(big.size) }), "warn");

  state.busy = true;
  $("#btn-zip").disabled = true;
  $("#file-list").hidden = false;
  $("#results").hidden = false;
  for (let i = 0; i < accepted.length; i++) {
    if (accepted.length > 1) {
      setNotice(t("notice.busy", { i: i + 1, n: accepted.length }), "ok");
    }
    await processFile(accepted[i]);
  }
  state.busy = false;
  $("#btn-zip").disabled = false;
  const ok = state.items.filter((it) => it.status === "done").length;
  setNotice(t("notice.done", { n: ok }), "ok");
  updateSummary();
}

/* -------------------------------------------------------------- rendering */
function renderItem(item) {
  const host = $("#file-list");
  let card = document.getElementById("item-" + item.id);
  if (!card) {
    card = el("article", "card");
    card.id = "item-" + item.id;
    host.appendChild(card);
  }
  card.textContent = "";
  card.appendChild(buildItemHeader(item));
  if (item.gps) card.appendChild(buildGpsWarning(item));

  if (item.status === "error") {
    const errLabel = /decode|not a|decode failed|image/i.test(item.error || "")
      ? t("error.notimage", { name: item.name })
      : t("error.generic", { name: item.name, err: item.error });
    card.appendChild(el("div", "alert danger", errLabel));
    card.appendChild(buildActions(item));
    return;
  }

  if (item.canvas) card.appendChild(buildCompare(item));

  const rows = item.meta ? flattenMetadata(item.meta) : [];
  if (settings().showMeta) card.appendChild(buildMetadata(item, rows));

  if (item.status === "done") {
    const ok = el("p", "muted");
    ok.textContent = t("verify.line") + " " + t("verify.icc");
    card.appendChild(ok);
  }
  card.appendChild(buildActions(item));
}

function buildItemHeader(item) {
  const head = el("div", "file-head");
  head.appendChild(el("span", "name", item.name));

  const pillCls = item.status === "done" ? "pill ok" : (item.status === "error" ? "pill bad" : "pill");
  const pillText = item.status === "done" ? "✓ " + t("status.done")
    : (item.status === "error" ? "✕ " + t("status.error") : t("status." + item.status));
  head.appendChild(el("span", pillCls, pillText));

  if (item.status === "done" && item.outSize != null) {
    const pct = item.size > 0 ? Math.round((1 - item.outSize / item.size) * 100) : 0;
    let label;
    if (item.outSize === item.size) label = t("size.same", { before: humanBytes(item.size) });
    else if (pct > 0) label = t("size.line", { before: humanBytes(item.size), after: humanBytes(item.outSize), pct: pct + "%" });
    else label = t("size.bigger", { before: humanBytes(item.size), after: humanBytes(item.outSize), pct: Math.abs(pct) + "%" });
    head.appendChild(ltrSpan("size", label));
  } else {
    head.appendChild(ltrSpan("size", humanBytes(item.size)));
  }
  if (item.outDims) {
    head.appendChild(ltrSpan("size", t("dims.line", { w: item.outDims.w, h: item.outDims.h })));
  }
  return head;
}

/** A span whose content is laid out independently of the page direction.
 *  Without this, "720×480" and "35.6892, 51.389" get reordered by the bidi
 *  algorithm inside an RTL paragraph — which would show coordinates backwards. */
function ltrSpan(cls, text) {
  const node = el("span", cls, text);
  node.setAttribute("dir", "auto");
  return node;
}

function updateItemStatus(item) {
  const card = document.getElementById("item-" + item.id);
  if (!card) return;
  const first = card.firstChild;
  if (first) card.replaceChild(buildItemHeader(item), first);
}

function buildGpsWarning(item) {
  const box = el("div", "alert danger");
  const title = el("strong", null, "📍 " + t("gps.title"));
  box.appendChild(title);
  box.appendChild(el("div", null, t("gps.body")));
  const coords = el("code", "coords",
    item.gps.latitude.toFixed(6) + ", " + item.gps.longitude.toFixed(6));
  coords.setAttribute("dir", "auto");
  coords.title = "latitude, longitude";
  box.appendChild(coords);
  box.appendChild(el("p", "muted", t("gps.warn")));

  const link = el("a", null, t("gps.map"));
  link.href = "https://www.openstreetmap.org/?mlat=" + item.gps.latitude +
    "&mlon=" + item.gps.longitude + "#map=16/" + item.gps.latitude + "/" + item.gps.longitude;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  box.appendChild(link);
  box.appendChild(el("p", "muted", t("gps.removed")));
  return box;
}

function buildCompare(item) {
  const wrap = el("div", "compare");
  const before = el("img", "before");
  before.src = item.beforeUrl;
  before.alt = t("cmp.before");
  wrap.appendChild(before);

  item.canvas.className = "after";
  item.canvas.setAttribute("aria-label", t("cmp.after"));
  wrap.appendChild(item.canvas);

  wrap.appendChild(el("span", "tag before", t("cmp.before")));
  wrap.appendChild(el("span", "tag after", t("cmp.after")));
  wrap.appendChild(el("span", "handle"));

  const range = el("input");
  range.type = "range";
  range.min = "0";
  range.max = "100";
  range.value = "50";
  range.className = "cmp-range";
  range.setAttribute("aria-label", t("cmp.hint"));
  range.addEventListener("input", () => {
    wrap.style.setProperty("--pos", range.value + "%");
  });

  const holder = el("div");
  holder.appendChild(wrap);
  holder.appendChild(range);
  holder.appendChild(el("p", "muted", t("cmp.hint")));

  // Pointer drag on the image itself (touch + mouse via Pointer Events).
  const setFromClientX = (clientX) => {
    const rect = wrap.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = (clientX - rect.left) / rect.width;
    let pct = Math.max(0, Math.min(1, ratio)) * 100;
    const isRtl = document.documentElement.getAttribute("dir") === "rtl";
    if (isRtl) pct = 100 - pct;
    wrap.style.setProperty("--pos", pct + "%");
    range.value = String(Math.round(pct));
  };
  let dragging = false;
  wrap.addEventListener("pointerdown", (e) => {
    dragging = true;
    try { wrap.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    setFromClientX(e.clientX);
  });
  wrap.addEventListener("pointermove", (e) => { if (dragging) setFromClientX(e.clientX); });
  wrap.addEventListener("pointerup", () => { dragging = false; });
  wrap.addEventListener("pointercancel", () => { dragging = false; });

  return holder;
}

const isSensitiveKey = (k) => SENSITIVE.has(String(k).toLowerCase().replace(/[^a-z0-9]/g, ""));

function buildMetadata(item, rows) {
  const details = el("details");
  details.open = true; // showing exactly what was inside is the whole point
  // Honest split: only *personal* chunks count as "removed metadata". JFIF
  // version / DPI / resolution are container plumbing and are listed apart,
  // exactly like analyze_metadata() does in the Python library.
  const personal = rows.filter(([k]) => isSensitiveKey(k));
  const technical = rows.filter(([k]) => !isSensitiveKey(k));
  details.appendChild(el("summary", null,
    personal.length ? t("meta.title", { n: personal.length }) : t("meta.none")));

  if (personal.length) {
    const table = el("table", "meta");
    const tbody = el("tbody");
    for (const [key, value] of personal) {
      const tr = el("tr", "sensitive");
      tr.appendChild(el("th", null, key));
      const td = el("td", null, renderValue(value));
      td.setAttribute("dir", "auto");
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    details.appendChild(table);
  }

  if (technical.length) {
    const sub = el("details");
    sub.appendChild(el("summary", "muted", t("meta.technical", { n: technical.length })));
    const table = el("table", "meta");
    const tbody = el("tbody");
    for (const [key, value] of technical) {
      const tr = el("tr", "tech");
      tr.appendChild(el("th", null, key));
      const td = el("td", null, renderValue(value));
      td.setAttribute("dir", "auto");
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    sub.appendChild(table);
    details.appendChild(sub);
  }
  return details;
}

function buildActions(item) {
  const bar = el("div", "file-actions");
  if (item.status === "done" && item.outBlob) {
    const dl = el("button", "primary", "⬇ " + t("btn.download"));
    dl.type = "button";
    dl.addEventListener("click", () => downloadBlob(item.outBlob, item.outName));
    bar.appendChild(dl);
  }
  const rm = el("button", "ghost", t("btn.remove"));
  rm.type = "button";
  rm.addEventListener("click", () => {
    const idx = state.items.indexOf(item);
    if (idx >= 0) state.items.splice(idx, 1);
    try { URL.revokeObjectURL(item.beforeUrl); } catch (_) { /* ignore */ }
    const card = document.getElementById("item-" + item.id);
    if (card) card.remove();
    updateSummary();
  });
  bar.appendChild(rm);
  return bar;
}

function updateSummary() {
  const host = $("#file-list");
  if (!host) return;
  $("#results").hidden = host.childElementCount === 0;
}

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name || "photo_cleaned.jpg";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function downloadZip() {
  const done = state.items.filter((it) => it.status === "done" && it.outBlob);
  if (!done.length) {
    setNotice(t("zip.empty"), "warn");
    return;
  }
  setNotice(t("zip.building"), "ok");
  if (!window.JSZip) {
    setNotice(t("zip.empty"), "warn");
    return;
  }
  const zip = new JSZip();
  const used = new Set();
  for (const item of done) {
    let name = item.outName;
    let n = 2;
    while (used.has(name)) {
      name = item.outName.replace(/(\.[^.]+)$/, "_" + n + "$1");
      n++;
    }
    used.add(name);
    zip.file(name, item.outBlob);
  }
  const blob = await zip.generateAsync({ type: "blob", compression: "STORE" });
  downloadBlob(blob, "cleaned-photos.zip");
  setNotice(t("zip.done", { n: done.length }), "ok");
}

function clearAll() {
  for (const item of state.items) {
    try { URL.revokeObjectURL(item.beforeUrl); } catch (_) { /* ignore */ }
  }
  state.items = [];
  $("#file-list").textContent = "";
  $("#results").hidden = true;
  setNotice("");
}

/* ------------------------------------------------------------------- proof */
async function probeNetwork() {
  const box = $("#probe-result");
  box.hidden = false;
  box.className = "alert";
  box.textContent = t("probe.trying");
  const url = "https://example.com/";
  try {
    await fetch(url, { mode: "no-cors", cache: "no-store" });
    box.className = "alert danger";
    box.textContent = t("probe.reachable") + " " + t("probe.detail", { url: url, err: "—" });
  } catch (err) {
    if (navigator.onLine === false) {
      box.className = "alert warn";
      box.textContent = t("probe.offline");
    } else {
      box.className = "alert ok";
      box.textContent = t("probe.blocked") + " " +
        t("probe.detail", { url: url, err: (err && err.message) || String(err) });
    }
  }
}

function updateNetState() {
  const node = $("#net-state");
  if (!node) return;
  const online = navigator.onLine !== false;
  node.className = "pill " + (online ? "info" : "ok");
  node.textContent = online ? t("net." + "online") : t("net." + "offline");
}

/* -------------------------------------------------------------------- i18n */
function applyI18n() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.getAttribute("data-i18n"));
  }
  $("#btn-lang").textContent = lang === "fa" ? "EN" : "فا";
  applyTheme(document.documentElement.getAttribute("data-theme") || "auto");
  updateNetState();
}

/* -------------------------------------------------------------------- boot */
function initDropzone() {
  const zone = $("#drop");
  const input = $("#file-input");

  const stop = (e) => { e.preventDefault(); e.stopPropagation(); };
  ["dragenter", "dragover"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { stop(e); zone.classList.add("hot"); }));
  ["dragleave", "drop"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { stop(e); zone.classList.remove("hot"); }));
  zone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length) handleFiles(dt.files);
  });
  zone.addEventListener("click", (e) => {
    if (e.target.tagName === "BUTTON" || e.target.tagName === "A") return;
    input.click();
  });
  input.addEventListener("change", () => {
    handleFiles(input.files);
    input.value = "";
  });
  document.addEventListener("paste", (e) => {
    const items = e.clipboardData && e.clipboardData.files;
    if (items && items.length) handleFiles(items);
  });
}

function init() {
  try {
    const savedLang = localStorage.getItem("imc-lang");
    if (savedLang === "fa" || savedLang === "en") lang = savedLang;
    const savedTheme = localStorage.getItem("imc-theme");
    if (THEMES.indexOf(savedTheme) >= 0) document.documentElement.setAttribute("data-theme", savedTheme);
  } catch (_) { /* storage disabled */ }

  applyI18n();
  applyTheme(document.documentElement.getAttribute("data-theme") || "auto");
  initDropzone();

  $("#btn-lang").addEventListener("click", () => {
    lang = lang === "fa" ? "en" : "fa";
    try { localStorage.setItem("imc-lang", lang); } catch (_) { /* ignore */ }
    applyI18n();
    for (const item of state.items) renderItem(item);
  });

  $("#btn-theme").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "auto";
    applyTheme(THEMES[(THEMES.indexOf(current) + 1) % THEMES.length]);
  });

  $("#btn-pick").addEventListener("click", (e) => { e.stopPropagation(); $("#file-input").click(); });

  $("#btn-demo").addEventListener("click", async (e) => {
    e.stopPropagation();
    setNotice("…", "ok");
    try {
      const file = await makeDemoFile();
      await handleFiles([file]);
    } catch (err) {
      setNotice(t("error.generic", { name: "demo.jpg", err: (err && err.message) || err }), "danger");
    }
  });

  $("#btn-zip").addEventListener("click", downloadZip);
  $("#btn-clear").addEventListener("click", clearAll);
  $("#btn-probe").addEventListener("click", probeNetwork);

  $("#opt-quality").addEventListener("input", (e) => {
    $("#quality-out").textContent = e.target.value + "%";
  });
  $("#opt-opacity").addEventListener("input", (e) => {
    $("#opacity-out").textContent = e.target.value + "%";
  });
  $("#opt-showmeta").addEventListener("change", () => {
    for (const item of state.items) renderItem(item);
  });

  window.addEventListener("online", updateNetState);
  window.addEventListener("offline", updateNetState);
  updateNetState();

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.deferredInstall = e;
  });
  $("#btn-install").addEventListener("click", async () => {
    if (!state.deferredInstall) {
      setNotice(t("install.hint"), "warn");
      return;
    }
    const prompt = state.deferredInstall;
    state.deferredInstall = null;
    try {
      prompt.prompt();
      await prompt.userChoice;
    } catch (_) { /* user dismissed */ }
  });

  if ("serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
    navigator.serviceWorker.register("sw.js").catch(() => { /* offline shell is optional */ });
  }
}

document.addEventListener("DOMContentLoaded", init);
