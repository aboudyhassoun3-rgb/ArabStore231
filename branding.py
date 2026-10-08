# -*- coding: utf-8 -*-
"""مولّد صور المنتجات بالهوية البصرية للمتجر (SVG خفيف، يعمل محلياً وعلى Supabase)."""
import hashlib

STORE_MARK = "ARAB STORE"

PALETTES = [
    ("#7c5cff", "#2a1a5e"), ("#f6c453", "#8a4b00"), ("#ff1a3c", "#5e0a1a"),
    ("#2dd4bf", "#07453c"), ("#4f8cff", "#0a245e"), ("#ff7ad9", "#5e0a44"),
    ("#34d399", "#06452e"), ("#ff9d5c", "#5e2a0a"),
]

EMOJI_MAP = [
    ("فري فاير", "🔥"), ("free fire", "🔥"), ("booyah", "🔥"),
    ("ببجي", "🎯"), ("pubg", "🎯"),
    ("فالورانت", "🔫"), ("valorant", "🔫"), ("vp", "🔫"),
    ("فورتنايت", "🪂"), ("fortnite", "🪂"),
    ("كود موبايل", "🔫"), ("call of duty", "🔫"), ("codm", "🔫"),
    ("بلود سترايك", "🔫"), ("blood strike", "🔫"),
    ("فارلايت", "🚀"), ("farlight", "🚀"),
    ("موبايل ليجند", "🎮"), ("mobile legends", "🎮"),
    ("فيفا", "⚽"), ("fifa", "⚽"), ("fc ", "⚽"), ("efootball", "⚽"),
    ("روبلوكس", "🧱"), ("roblox", "🧱"),
    ("هونكاي", "✨"), ("honkai", "✨"), ("oneiric", "✨"),
    ("جينشن", "✨"), ("genshin", "✨"), ("غينشن", "✨"),
    ("لودو", "🎲"), ("ludo", "🎲"),
    ("مارفل", "🦸"), ("marvel", "🦸"),
    ("جواكر", "🃏"), ("jawaker", "🃏"),
    ("بلياردو", "🎱"), ("8ball", "🎱"), ("8 ball", "🎱"),
    ("ماينكرافت", "⛏️"), ("minecraft", "⛏️"),
    ("شطرنج", "♟️"), ("شيش", "🎲"),
    ("فورتنايت", "🪂"), ("fortnite", "🪂"),
    ("كود موبايل", "🔫"), ("call of duty", "🔫"), ("cod", "🔫"),
    ("فيفا", "⚽"), ("fifa", "⚽"), ("fc ", "⚽"), ("efootball", "⚽"),
    ("روبلوكس", "🧱"), ("roblox", "🧱"),
    ("ماينكرافت", "⛏️"), ("minecraft", "⛏️"),
    ("آيتونز", "🎵"), ("itunes", "🎵"), ("apple", "🎵"),
    ("غوغل", "▶️"), ("google play", "▶️"),
    ("بلايستيشن", "🎮"), ("playstation", "🎮"), ("psn", "🎮"),
    ("اكس بوكس", "🕹️"), ("xbox", "🕹️"),
    ("ستيم", "🎮"), ("steam", "🎮"),
    ("امازون", "📦"), ("amazon", "📦"),
    ("ريزر", "🖱️"), ("razer", "🖱️"),
    ("نتفلكس", "🎬"), ("netflix", "🎬"),
    ("شاهد", "📺"), ("shahid", "📺"),
    ("برايم", "📺"), ("prime", "📺"),
    ("ديزني", "🌟"), ("disney", "🌟"),
    ("او اس ان", "📺"), ("osn", "📺"),
    ("كرانشي", "🍥"), ("crunchy", "🍥"),
    ("يوتيوب", "▶️"), ("youtube", "▶️"),
    ("سبوتفاي", "🎵"), ("spotify", "🎵"),
    ("انغامي", "🎵"), ("anghami", "🎵"),
    ("ديزر", "🎵"), ("deezer", "🎵"),
    ("جوهرة", "💎"), ("جواهر", "💎"), ("diamonds", "💎"), ("diamond", "💎"),
    ("ذهب", "🪙"), ("gold", "🪙"),
    ("عملة", "🪙"), ("coins", "🪙"), ("coin", "🪙"),
    ("شدة", "🎯"), ("شدات", "🎯"),
    ("قسيمة", "🎫"), ("voucher", "🎫"), ("vouchers", "🎫"),
    ("تذكرة", "🎟️"), ("ticket", "🎟️"),
    ("عضوية", "👑"), ("membership", "👑"),
    ("باس", "👑"), ("pass", "👑"),
    ("شحن", "💳"), ("رصيد", "📶"), ("بطاقة", "💳"),
    ("فيزا", "💳"), ("visa", "💳"),
    ("متابع", "👥"), ("لايك", "❤️"), ("مشاهد", "👁️"),
    ("واتساب", "📱"), ("whatsapp", "📱"),
    ("تيليجرام", "✈️"), ("telegram", "✈️"),
    ("انست", "📸"), ("instagram", "📸"),
    ("تيك توك", "🎵"), ("tiktok", "🎵"),
    ("غوغل", "▶️"), ("google play", "▶️"),
    ("بلايستيشن", "🎮"), ("playstation", "🎮"), ("psn", "🎮"),
    ("اكس بوكس", "🕹️"), ("xbox", "🕹️"),
    ("ستيم", "🎮"), ("steam", "🎮"),
    ("نتفليكس", "🎬"), ("netflix", "🎬"),
    ("شاهد", "📺"), ("شاهد", "📺"), ("disney", "🌟"),
    ("ديسكورد", "💬"), ("discord", "💬"), ("nitro", "💬"),
    ("تيليجرام", "✈️"), ("telegram", "✈️"), (" premium", "✈️"),
    ("واتساب", "📱"), ("انستا", "📸"), ("instagram", "📸"),
    ("تيك توك", "🎵"), ("tiktok", "🎵"),
    ("شحن", "💳"), ("رصيد", "💳"), ("بطاقة", "💳"),
    ("متابع", "👥"), ("لايك", "❤️"), ("مشاهد", "👁️"),
]


def pick_emoji(name):
    low = (name or "").lower()
    for key, emo in EMOJI_MAP:
        if key in low or key in (name or ""):
            return emo
    return "🎮"


def pick_palette(name):
    h = int(hashlib.md5((name or "").encode("utf-8")).hexdigest(), 16)
    return PALETTES[h % len(PALETTES)]


def short_name(name, limit=22):
    name = (name or "").strip()
    return name if len(name) <= limit else name[:limit - 1] + "…"


def _escape_xml(text):
    return ((text or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def wrap_title(name, per_line=16):
    """يقسّم الاسم على سطرين متوازنين كحد أقصى بدل قصّه."""
    text = (name or "").strip() or "منتج"
    if len(text) <= per_line:
        return [text]
    words = text.split()
    if len(words) == 1:
        return [words[0][:per_line], words[0][per_line:per_line * 2]]
    # نقطة التقسيم التي توازن طول السطرين
    best, best_diff, acc = 1, None, 0
    for i, w in enumerate(words[:-1]):
        acc += len(w) + 1
        diff = abs(acc - len(text) / 2)
        if best_diff is None or diff < best_diff:
            best, best_diff = i + 1, diff
    lines = [" ".join(words[:best]), " ".join(words[best:])]
    # سطر ما زال طويلاً جداً (كلمة مفردة عملاقة): اقسمه قسراً
    fixed = []
    for ln in lines:
        while len(ln) > per_line + 8:
            fixed.append(ln[:per_line + 8])
            ln = ln[per_line + 8:]
        if ln:
            fixed.append(ln)
    return fixed[:2] or ["منتج"]


def build_product_svg(name, store_name=None):
    """يرجع نص SVG مكتفي ذاتياً: تدرّج + إيموجي + الاسم (حتى سطرين) + شريط المتجر."""
    c1, c2 = pick_palette(name or "store")
    emo = pick_emoji(name or "")
    brand = _escape_xml((store_name or STORE_MARK).strip() or STORE_MARK)
    lines = [_escape_xml(ln) for ln in wrap_title(name or "منتج")]
    gid = hashlib.md5(((name or "") + c1).encode("utf-8")).hexdigest()[:8]
    # خط أصغر كلما طال النص، وموضع مرن حسب عدد الأسطر
    longest = max((len(ln) for ln in lines), default=0)
    font_size = 46 if longest <= 14 else (40 if longest <= 18 else 34)
    if len(lines) == 1:
        title_svg = f'<text x="300" y="275" text-anchor="middle" font-size="{font_size}" font-weight="bold" fill="#ffffff" font-family="Cairo, Tahoma, Arial, sans-serif" filter="url(#sh{gid})">{lines[0]}</text>'
    else:
        title_svg = (f'<text x="300" y="248" text-anchor="middle" font-size="{font_size}" font-weight="bold" fill="#ffffff" font-family="Cairo, Tahoma, Arial, sans-serif" filter="url(#sh{gid})">{lines[0]}</text>'
                     f'<text x="300" y="292" text-anchor="middle" font-size="{font_size}" font-weight="bold" fill="#ffffff" font-family="Cairo, Tahoma, Arial, sans-serif" filter="url(#sh{gid})">{lines[1]}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
<defs><linearGradient id="g{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>
<filter id="sh{gid}" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.45"/></filter></defs>
<rect width="600" height="400" rx="28" fill="url(#g{gid})"/>
<circle cx="520" cy="60" r="120" fill="#ffffff" opacity="0.10"/><circle cx="80" cy="340" r="150" fill="#ffffff" opacity="0.08"/><circle cx="500" cy="330" r="60" fill="#000000" opacity="0.12"/>
<text x="300" y="175" text-anchor="middle" font-size="110" filter="url(#sh{gid})">{emo}</text>
{title_svg}
<rect x="185" y="312" width="230" height="52" rx="26" fill="#000000" opacity="0.35"/>
<text x="300" y="347" text-anchor="middle" font-size="26" font-weight="bold" fill="#f6c453" font-family="Arial, sans-serif" letter-spacing="3">★ {brand} ★</text>
</svg>"""


def brand_filename(name):
    return "brand-" + hashlib.md5((name or "").encode("utf-8")).hexdigest()[:12] + ".svg"
