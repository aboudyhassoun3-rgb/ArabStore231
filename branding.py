# -*- coding: utf-8 -*-
"""هوية صور المتجر الموحدة (ARAB STORE Luxury):
- كل الصور بنفس الستايل الفخم: كحلي داكن + توهج أحمر + ذهبي.
- أي اسم عربي يُحوَّل تلقائياً لإنجليزي، ولا يُكتب أي حرف عربي داخل الصورة أبداً.
- المنتجات المعروفة تحصل على شعارها الرسمي المبسّط (monogram) بألوانها.
- build_precise_prompt() يولّد برومبت إنجليزي دقيقاً لأي API توليد خارجي بنفس الهوية.
"""
import hashlib
import re

STORE_MARK = "ARAB STORE"

# هوية المتجر الثابتة — كل الصور منها حصراً لتتناسق 100%
STORE_BG_TOP = "#141a2e"
STORE_BG_BOTTOM = "#0b0f19"
STORE_ACCENT = "#ff1a3c"
STORE_GOLD = "#ffc24b"
STORE_GOLD_2 = "#ff9f1c"
STORE_TEXT = "#f3f6fa"

PALETTES = [
    ("#7c5cff", "#2a1a5e"), ("#f6c453", "#8a4b00"), ("#ff1a3c", "#5e0a1a"),
    ("#2dd4bf", "#07453c"), ("#4f8cff", "#0a245e"), ("#ff7ad9", "#5e0a44"),
    ("#34d399", "#06452e"), ("#ff9d5c", "#5e2a0a"),
]

# لوحة موحدة بديلة (تُستخدم عند طلب التناسق الكامل مع المتجر)
UNIFIED_BG = (STORE_BG_TOP, STORE_BG_BOTTOM)

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


# ------------------------------------------------------------------
# التعريب → إنجليزي: لا يُكتب أي حرف عربي داخل الصور أبداً
# ------------------------------------------------------------------
# أسماء المنتجات/الألعاب الشائعة → اسمها الإنجليزي الرسمي
AR_EN_NAMES = [
    ("فري فاير", "FREE FIRE"), ("فرى فاير", "FREE FIRE"),
    ("ببجي", "PUBG MOBILE"), ("بوبجي", "PUBG MOBILE"),
    ("موبايل", "MOBILE"),
    ("فورتنايت", "FORTNITE"),
    ("كود موبايل", "CALL OF DUTY"), ("كول اوف ديوتي", "CALL OF DUTY"),
    ("بلود سترايك", "BLOOD STRIKE"),
    ("فارلايت", "FARLIGHT 84"),
    ("موبايل ليجند", "MOBILE LEGENDS"), ("موبايل ليجيند", "MOBILE LEGENDS"),
    ("فيفا", "EA FC"), ("إي فوتبول", "EFOOTBALL"), ("اي فوتبول", "EFOOTBALL"),
    ("روبلوكس", "ROBLOX"),
    ("هونكاي", "HONKAI"), ("غينشن", "GENSHIN"), ("جينشن", "GENSHIN"),
    ("لودو", "LUDO"), ("مارفل", "MARVEL"),
    ("جواكر", "JAWAKER"), ("بلياردو", "8 BALL POOL"),
    ("ماينكرافت", "MINECRAFT"), ("شطرنج", "CHESS"),
    ("آيتونز", "ITUNES"), ("غوغل بلاي", "GOOGLE PLAY"), ("جوجل بلاي", "GOOGLE PLAY"),
    ("بلايستيشن", "PLAYSTATION"), ("بلاي ستيشن", "PLAYSTATION"),
    ("اكس بوكس", "XBOX"), ("إكس بوكس", "XBOX"),
    ("ستيم", "STEAM"), ("امازون", "AMAZON"),
    ("ريزر", "RAZER"), ("نتفلكس", "NETFLIX"),
    ("شاهد", "SHAHID"), ("برايم", "PRIME VIDEO"),
    ("ديزني", "DISNEY+"), ("او اس ان", "OSN"),
    ("كرانشي", "CRUNCHYROLL"), ("يوتيوب", "YOUTUBE"),
    ("سبوتفاي", "SPOTIFY"), ("انغامي", "ANGHAMI"), ("ديزر", "DEEZER"),
    ("جوهرة", "DIAMONDS"), ("جواهر", "DIAMONDS"),
    ("ذهب", "GOLD"), ("دهب", "GOLD"),
    ("عملة", "COINS"), ("عملات", "COINS"),
    ("شدة", "UC"), ("شدات", "UC"),
    ("قسيمة", "VOUCHER"), ("قسائم", "VOUCHERS"),
    ("تذكرة", "TICKET"), ("تذاكر", "TICKETS"),
    ("عضوية", "MEMBERSHIP"), ("باس", "PASS"),
    ("شحن", "TOP UP"), ("رصيد", "BALANCE"), ("بطاقة", "CARD"), ("بطاقات", "CARDS"),
    ("فيزا", "VISA"),
    ("متابع", "FOLLOWERS"), ("متابعين", "FOLLOWERS"),
    ("لايك", "LIKES"), ("لايكات", "LIKES"),
    ("مشاهد", "VIEWS"), ("مشاهدات", "VIEWS"),
    ("واتساب", "WHATSAPP"), ("تيليجرام", "TELEGRAM"),
    ("انست", "INSTAGRAM"), ("انستا", "INSTAGRAM"),
    ("تيك توك", "TIKTOK"),
    ("قسم", "SECTION"), ("فرع", "BRANCH"), ("فرعي", "SUB"),
    ("سريع", "FAST"), ("جديد", "NEW"), ("مميز", "PREMIUM"),
    ("عروض", "OFFERS"), ("رئيسي", "MAIN"),
    ("شهر", "MONTH"), ("شهرية", "MONTHLY"), ("شهور", "MONTHS"),
    ("سنة", "YEAR"), ("سنوي", "YEARLY"),
    ("يوم", "DAY"), ("أسبوع", "WEEK"),
    ("مميزة", "PREMIUM"), ("ذهبية", "GOLD"),
    ("ألعاب", "GAMES"), ("العاب", "GAMES"),
    ("رقمية", "DIGITAL"),
    ("خدمات", "SERVICES"),
    ("التواصل", "SOCIAL"),
    ("اجتماعي", "SOCIAL"),
]

# حروف عربية → لاتينية (للأسماء غير المسجلة أعلاه)
AR_LETTERS = {
    "ا": "a", "أ": "a", "إ": "i", "آ": "aa", "ء": "a",
    "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh",
    "د": "d", "ذ": "th", "ر": "r", "ز": "z", "س": "s", "ش": "sh",
    "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh",
    "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "ة": "a", "و": "w", "ؤ": "o", "ي": "y", "ئ": "e", "ى": "a",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def to_english(name):
    """تحويل الاسم لإنجليزي صالح للكتابة داخل الصور (بدون أي حرف عربي).
    1) استبدال الأسماء المعروفة بأسمائها الرسمية.
    2) ترجمة حرف-بحرف لما تبقى، مع تنظيف نهائي صارم."""
    text = (name or "").strip()
    if not text:
        return "PRODUCT"
    low = text.lower()
    for ar, en in sorted(AR_EN_NAMES, key=lambda x: -len(x[0])):
        if ar in text or ar in low:
            text = text.replace(ar, f" {en} ")
            low = text.lower()
    # احذف "ال" التعريف الباقية (متصلة بكلمة عربية أو منفصلة) حتى لا تظهر كـ AL
    text = re.sub(r"(?<![\u0600-\u06FFA-Za-z])ال(?![A-Za-z])", "", text)
    out = []
    for ch in text:
        if _ARABIC_RE.match(ch):
            out.append(AR_LETTERS.get(ch, ""))
        else:
            out.append(ch)
    text = "".join(out)
    # أبقِ فقط: لاتيني + أرقام + مسافة + رموز آمنة للصور
    text = re.sub(r"[^A-Za-z0-9 +\-&'★]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -+&'")
    if not text:
        return "PRODUCT"
    # ادمج الكلمات المكررة المتجاورة (مثلاً: ببجي→PUBG MOBILE ثم موبايل→MOBILE)
    words, dedup = text.split(" "), []
    for w in words:
        if not dedup or dedup[-1].lower() != w.lower():
            dedup.append(w)
    text = " ".join(dedup)
    return text.upper()


def display_title(name, limit=26):
    """العنوان الإنجليزي النهائي للصورة (سطر أو سطران لاحقاً عبر wrap_title)."""
    en = to_english(name)
    if len(en) <= limit:
        return en
    # قص ذكي عند حد الكلمات بدل منتصف الكلمة
    cut = en[:limit].rsplit(" ", 1)
    head = cut[0] if len(cut) > 1 and len(cut[0]) >= limit - 8 else en[:limit]
    return head.rstrip() + "…"


# ------------------------------------------------------------------
# الشعارات الرسمية المبسطة للمنتجات المعروفة (monogram فخم بألوان البراند)
# ------------------------------------------------------------------
# key: (نص الشعار داخل الدائرة, لون الخلفية, لون النص)
OFFICIAL_MARKS = [
    (("pubg", "ببجي"), ("PUBG", "#f2a900", "#1a1a1a")),
    (("free fire", "فري فاير", "فرى فاير"), ("FF", "#ff6b00", "#ffffff")),
    (("fortnite", "فورتنايت"), ("FN", "#7c3aed", "#ffffff")),
    (("call of duty", "كود موبايل", "كول اوف"), ("COD", "#3a3a3a", "#ffd23f")),
    (("blood strike", "بلود سترايك"), ("BS", "#c40f28", "#ffffff")),
    (("farlight", "فارلايت"), ("F84", "#0ea5e9", "#ffffff")),
    (("mobile legends", "موبايل ليجند", "موبايل ليجيند"), ("ML", "#2563eb", "#ffffff")),
    (("ea fc", "فيفا"), ("FC", "#16a34a", "#ffffff")),
    (("efootball", "اي فوتبول", "إي فوتبول"), ("eF", "#0ea5e9", "#ffffff")),
    (("roblox", "روبلوكس"), ("R", "#e11d48", "#ffffff")),
    (("honkai", "هونكاي"), ("H", "#a78bfa", "#1a1a2e")),
    (("genshin", "جينشن", "غينشن"), ("G", "#38bdf8", "#0b1e33")),
    (("ludo", "لودو"), ("L", "#f59e0b", "#1a1a1a")),
    (("jawaker", "جواكر"), ("J", "#10b981", "#ffffff")),
    (("8 ball", "8ball", "بلياردو"), ("8", "#111827", "#ffffff")),
    (("minecraft", "ماينكرافت"), ("M", "#65a30d", "#ffffff")),
    (("itunes", "آيتونز"), ("♪", "#fa2d48", "#ffffff")),
    (("google play", "غوغل بلاي", "جوجل بلاي"), ("▶", "#01875f", "#ffffff")),
    (("playstation", "بلايستيشن", "بلاي ستيشن"), ("PS", "#0070d1", "#ffffff")),
    (("xbox", "اكس بوكس", "إكس بوكس"), ("X", "#107c10", "#ffffff")),
    (("steam", "ستيم"), ("S", "#1b2838", "#c7d5e0")),
    (("netflix", "نتفلكس"), ("N", "#e50914", "#ffffff")),
    (("shahid", "شاهد"), ("S", "#00b8a9", "#ffffff")),
    (("disney", "ديزني"), ("D+", "#113ccf", "#ffffff")),
    (("spotify", "سبوتفاي"), ("S", "#1db954", "#ffffff")),
    (("youtube", "يوتيوب"), ("▶", "#ff0000", "#ffffff")),
    (("tiktok", "تيك توك"), ("♪", "#111111", "#25f4ee")),
    (("whatsapp", "واتساب"), ("✆", "#25d366", "#ffffff")),
    (("telegram", "تيليجرام"), ("✈", "#229ed9", "#ffffff")),
    (("instagram", "انست"), ("◉", "#e1306c", "#ffffff")),
    (("visa", "فيزا"), ("V", "#1a1f71", "#ffffff")),
]


def official_mark(name):
    """يرجع (monogram, bg, fg) أو None إن لم يكن المنتج معروفاً."""
    low = (name or "").lower()
    for keys, mark in OFFICIAL_MARKS:
        for k in keys:
            if k and (k in low or k in (name or "")):
                return mark
    return None


# ------------------------------------------------------------------
# موسوعة الشعارات: وصف غني يُرسل للـ AI مع اسم اللعبة/المنتج ليفهم
# ما هو، ودوره، وتفاصيل شعاره وألوانه وعناصره الأيقونية بدقة.
# key: كلمات مطابقة — value: (الاسم الرسمي, ما هو, العناصر الأيقونية,
#                             الألوان الرسمية, وصف الشعار, دور العملة/المنتج)
# ------------------------------------------------------------------
BRAND_PROFILES = [
    (("pubg", "ببجي"),
     ("PUBG Mobile",
      "the world's most famous mobile battle royale shooter",
      "military soldier helmet (level-3 Spetsnaz helmet), golden frying pan, airdrop supply crate falling with parachute, orange smoke signals, war-torn battleground",
      "military tan khaki and dark charcoal with vivid orange #f2a900",
      "bold rugged stencil-style PUBG lettering with military attitude",
      "Unknown Cash (UC) is its in-game currency for outfits, gun skins, crates and the Royale Pass")),
    (("free fire", "فري فاير", "فرى فاير"),
     ("Free Fire",
      "Garena's fast-paced mobile battle royale",
      "orange-red flame swirl, airdrop boxes, graffiti street style, booyah fire energy, survival battleground vibes",
      "fiery orange #ff6b00, hot red and deep black",
      "flame-shaped FF mark burning in orange and white",
      "Diamonds are its top-up currency for characters, bundles, weapon skins and Luck Royale spins")),
    (("fortnite", "فورتنايت"),
     ("Fortnite",
      "epic cartoon-style battle royale with building mechanics",
      "purple storm clouds, supply llama pinata, battle bus balloon, V-Bucks cards, vibrant comic shading",
      "electric purple #7c3aed, cyan and bright yellow",
      "stylized runic FN letters",
      "V-Bucks buy battle-pass tiers, emotes and character skins")),
    (("call of duty", "كود موبايل", "كول اوف", "codm", "cod "),
     ("Call of Duty Mobile",
      "realistic military first-person shooter",
      "skull-masked special soldier, dog tags, night-vision green glow, helicopter and battlefield smoke",
      "gunmetal grey #3a3a3a with tactical yellow #ffd23f",
      "heavy stencil COD lettering",
      "CP Points unlock the battle pass, lucky draws and legendary weapons")),
    (("blood strike", "بلود سترايك"),
     ("Blood Strike",
      "stylish fast arena battle royale shooter",
      "red strike slash across the frame, striker operatives, muzzle flashes, urban combat zone",
      "blood red #c40f28, black and white",
      "sharp BS monogram cut by a red slash",
      "Gold top-up for operators, weapon blueprints and the Strike Pass")),
    (("farlight", "فارلايت"),
     ("Farlight 84",
      "futuristic hero shooter with capsule-drop entry",
      "space capsule landing pods, jetpacks, neon wasteland city, hero squad silhouettes",
      "sky blue #0ea5e9, orange and graphite",
      "angular F84 emblem",
      "Diamonds recruit heroes and upgrade futuristic gear")),
    (("mobile legends", "موبايل ليجند", "موبايل ليجيند", "mlbb"),
     ("Mobile Legends Bang Bang",
      " legendary 5v5 mobile MOBA arena",
      "blue-gold knight crest, crystal diamonds, epic lane battleground, hero statues",
      "royal blue #2563eb and champion gold",
      "regal ML crest",
      "Diamonds buy heroes, epic skins and emblem upgrades")),
    (("ea fc", "فيفا", "fc mobile", "fc 24", "fc 25", "fc26"),
     ("EA Sports FC Mobile",
      "the official mobile football simulation",
      "packed stadium at night, green pitch light beams, golden football, trophy confetti",
      "pitch green #16a34a, white and gold",
      "bold FC monogram in a shield",
      "FC Points open star packs and sign football legends")),
    (("efootball", "اي فوتبول", "إي فوتبول", "ايفوتبول"),
     ("eFootball",
      "Konami's free football simulation",
      "floodlit stadium, dynamic striker kick, blue energy ribbons",
      "electric blue #0ea5e9 and white",
      "sleek eFootball wordmark",
      "Coins sign Dream Team epics and legends")),
    (("roblox", "روبلوكس"),
     ("Roblox",
      "blocky user-created-games universe",
      "tilted square logo hole, blocky avatar builders, floating cubes, green Robux bills",
      "crimson #e11d48, dark grey and money green",
      "iconic tilted-square mark",
      "Robux spend on avatar items, game passes and animations")),
    (("honkai", "هونكاي"),
     ("Honkai Star Rail",
      "HoYoverse space-fantasy turn-based RPG",
      "astral express train flying through galaxies, starry rail tracks, warp portals",
      "lavender #a78bfa over midnight blue",
      "elegant H emblem with cosmic rings",
      "Oneiric Shards fund warp tickets for 5-star characters")),
    (("genshin", "جينشن", "غينشن"),
     ("Genshin Impact",
      "open-world elemental action RPG of Teyvat",
      "glowing elemental stars, teal wind glider wings, floating islands, ancient statues",
      "sky teal #38bdf8, white and deep blue",
      "starry Genshin gate emblem",
      "Genesis Crystals convert to wishes for heroes and weapons")),
    (("ludo", "لودو"),
     ("Ludo",
      "the classic family board game of tokens and dice",
      "giant rolling dice, red yellow green blue tokens racing home, playful board",
      "warm amber #f59e0b with classic four colors",
      "cheerful LUDO lettering",
      "Coins and gems buy arenas, dice skins and quick matches")),
    (("jawaker", "جواكر"),
     ("Jawaker",
      "the Arab world's cards and board games hub (tarneeb,sehha...)",
      "playing cards fan, golden card suits, VIP green table, token piles",
      "emerald #10b981 and gold",
      "rounded J mark in green",
      "Tokens enter VIP rooms, tournaments and exclusive tables")),
    (("8 ball", "8ball", "بلياردو", "pool"),
     ("8 Ball Pool",
      "the classic mobile billiards duel",
      "black 8-ball on green felt, crossed cues, chalk dust, neon arcade frame",
      "felt green with black-and-white ball contrast",
      "bold number-8 emblem",
      "Coins and cash enter high-stake matches and cue upgrades")),
    (("minecraft", "ماينكرافت"),
     ("Minecraft",
      "the blocky sandbox of infinite building",
      "grass dirt blocks, diamond pickaxe, creeper face, torch-lit caves",
      "creeper green #65a30d and earthy brown",
      "cracked-stone MINECRAFT lettering",
      "Minecoins unlock skins, texture packs and adventure maps")),
    (("itunes", "آيتونز"),
     ("iTunes / Apple Gift Card",
      "Apple credit for apps, games and subscriptions",
      "pink-red musical note, glowing gift card, app icons orbit",
      "Apple pink-red #fa2d48 on dark",
      "musical-note gift emblem",
      "credit tops up Apple ID for games, iCloud and subscriptions")),
    (("google play", "غوغل بلاي", "جوجل بلاي"),
     ("Google Play",
      "Android credit for games and apps",
      "colorful triangle play button (blue green yellow red), gift card glow",
      "play-store multicolor on dark",
      "triangle play emblem",
      "credit buys diamonds, UC and premium apps directly")),
    (("playstation", "بلايستيشن", "بلاي ستيشن", "psn"),
     ("PlayStation Store",
      "Sony gaming credit for PS4 and PS5",
      "blue galaxy with triangle circle cross square symbols, DualSense controller",
      "PlayStation blue #0070d1",
      "iconic PS shapes emblem",
      "wallet top-up buys games, PS Plus and add-ons")),
    (("xbox", "اكس بوكس", "إكس بوكس", "game pass"),
     ("Xbox",
      "Microsoft gaming world with Game Pass",
      "glowing green X sphere, controller, game library wall",
      "Xbox green #107c10 on black",
      "luminous X orb emblem",
      "credit funds Game Pass, games and in-game content")),
    (("steam", "ستيم"),
     ("Steam Wallet",
      "PC gaming credit for thousands of games",
      "dark steel gear-piston arm, wallet code card, game covers collage",
      "steel blue-grey #1b2838 with pale blue",
      "mechanical arm emblem",
      "wallet codes buy games, skins and DLCs")),
    (("netflix", "نتفلكس"),
     ("Netflix",
      "world-leading movie and series streaming",
      "red N ribbon over cinematic film glow, popcorn and premiere lights",
      "signature red #e50914 on black",
      "tall red N emblem",
      "gift cards extend premium viewing plans")),
    (("shahid", "شاهد"),
     ("Shahid VIP",
      "Arabic series and cinema streaming",
      "teal play glow with Arabic drama spotlights, cinema curtains",
      "teal #00b8a9 on dark",
      "modern S emblem",
      "VIP subscription unlocks exclusive series ad-free")),
    (("disney", "ديزني"),
     ("Disney+",
      "magic streaming of Disney, Marvel and Star Wars",
      "blue arch with sparkling stars, castle silhouette, heroes collage",
      "magic blue #113ccf with starlight",
      "starry D+ arch emblem",
      "subscription opens the full magic library")),
    (("spotify", "سبوتفاي"),
     ("Spotify Premium",
      "music streaming without limits",
      "green circle of pulsing sound waves, concert lights, floating notes",
      "vivid green #1db954 on black",
      "waves-in-circle emblem",
      "Premium removes ads with offline downloads")),
    (("youtube", "يوتيوب"),
     ("YouTube Premium",
      "ad-free video and music streaming",
      "red play button over dark cinema glow, creator studio vibes",
      "pure red #ff0000 on black",
      "rounded red play emblem",
      "Premium removes ads with background play")),
    (("tiktok", "تيك توك"),
     ("TikTok",
      "short-video platform with live gifts and coins",
      "black musical note with cyan-pink glitch, golden coins rain, stage spotlights",
      "black with neon cyan #25f4ee and pink",
      "glitch note emblem",
      "Coins recharge funds live gifts and promotions")),
    (("whatsapp", "واتساب"),
     ("WhatsApp",
      "instant messaging and virtual numbers",
      "green chat bubble with phone handset, floating message ticks, SIM card",
      "WhatsApp green #25d366",
      "phone-in-bubble emblem",
      "numbers activate accounts and verifications worldwide")),
    (("telegram", "تيليجرام", "تليجرام"),
     ("Telegram",
      "cloud messaging with stars and premium",
      "blue paper plane flying over clouds, golden stars trail",
      "Telegram blue #229ed9",
      "paper-plane emblem",
      "Stars and Premium unlock gifts, stories and extra limits")),
    (("instagram", "انست", "انستغرام"),
     ("Instagram growth services",
      "followers, likes and views boosts",
      "gradient camera glyph, hearts storm, rising follower chart",
      "pink-purple-orange gradient",
      "camera emblem",
      "packages grow followers, likes and reel views fast")),
    (("visa", "فيزا"),
     ("Visa payment card",
      "global online payment top-up",
      "navy-gold premium bank card with chip, secure lock glow",
      "deep navy #1a1f71 and gold",
      "italic VISA lettering",
      "credit enables secure worldwide purchases")),
]


def _brand_profile(name):
    """يرجع ملف البراند المطابق أو None."""
    low = (name or "").lower()
    for keys, prof in BRAND_PROFILES:
        for k in keys:
            if k and (k in low or k in (name or "")):
                return prof
    return None


def describe_brand(name):
    """وصف إنجليزي غني للـ AI: ما هو المنتج/اللعبة، دوره، شعاره وألوانه وعناصره.
    يرجع '' للمنتجات غير المعروفة (يُستخدم describe_subject بدلاً منه)."""
    prof = _brand_profile(name)
    if not prof:
        return ""
    official, kind, visuals, colors, emblem, role = prof
    return (f"{official} — {kind}. Iconic visuals: {visuals}. "
            f"Official colors: {colors}. Logo: {emblem}. Role: {role}.")


def describe_subject(name):
    """وصف بصري ذكي للمنتجات غير المعروفة: يستنتج نوع المحتوى
    (عملة/اشتراك/أرقام/متابعين...) ويصفه للـ AI بدقة."""
    low = (name or "").lower()
    if any(k in low for k in ("uc", "شدات")):
        item = "shiny golden UC coins piles with military glow"
    elif any(k in low for k in ("diamond", "diamonds", "جواهر", "جوهرة", "💎", "الماس")):
        item = "sparkling blue-white diamond crystals rain"
    elif any(k in low for k in ("gold", "ذهب", "ذهبي", "كوينز ذهب")):
        item = "gleaming gold bars and coins stacks"
    elif any(k in low for k in ("coin", "coins", "كوين", "كوينز", "عملات", "نقود")):
        item = "glowing game coins fountain"
    elif any(k in low for k in ("point", "points", "نقاط", "نقطة")):
        item = "luminous points tokens orbiting"
    elif any(k in low for k in ("follower", "followers", "متابع", "متابعين", "مشترك")):
        item = "crowd of follower avatars with a steep rising growth chart"
    elif any(k in low for k in ("like", "likes", "لايك", "لايكات", "اعجاب")):
        item = "storm of glossy red hearts and thumbs-up icons"
    elif any(k in low for k in ("view", "views", "مشاهد", "مشاهدات")):
        item = "play-button counters exploding upward"
    elif any(k in low for k in ("subscri", "اشتراك", "عضوية", "بريميوم", "premium", "vip")):
        item = "luxurious premium membership card with golden seal"
    elif any(k in low for k in ("number", "numbers", "رقم", "ارقام", "أرقام", "sim", "شريحة")):
        item = "modern SIM cards and smartphones with signal waves"
    elif any(k in low for k in ("card", "cards", "بطاقة", "بطاقات", "gift", "هدية", "كود", "voucher")):
        item = "elegant glowing gift card with ribbon and code sparks"
    elif any(k in low for k in ("pass", "royale", "الباس", "تذكرة", "season")):
        item = "golden season-pass ticket with confetti burst"
    else:
        item = "premium digital voucher chest with glowing treasures"
    return f"Showcase content: {item}."


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


def _lux_defs(gid):
    return (f'<defs>'
            f'<linearGradient id="g{gid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{STORE_BG_TOP}"/><stop offset="1" stop-color="{STORE_BG_BOTTOM}"/>'
            f'</linearGradient>'
            f'<radialGradient id="gl{gid}" cx="0.5" cy="0.28" r="0.75">'
            f'<stop offset="0" stop-color="{STORE_ACCENT}" stop-opacity="0.38"/>'
            f'<stop offset="0.55" stop-color="{STORE_ACCENT}" stop-opacity="0.08"/>'
            f'<stop offset="1" stop-color="{STORE_ACCENT}" stop-opacity="0"/>'
            f'</radialGradient>'
            f'<linearGradient id="gd{gid}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{STORE_GOLD}"/><stop offset="1" stop-color="{STORE_GOLD_2}"/>'
            f'</linearGradient>'
            f'<filter id="sh{gid}" x="-20%" y="-20%" width="140%" height="140%">'
            f'<feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.5"/>'
            f'</filter></defs>')


def _lux_frame(gid, subtitle="PREMIUM DIGITAL STORE"):
    sub = _escape_xml(subtitle)
    return (f'<rect width="600" height="400" rx="28" fill="url(#g{gid})"/>'
            f'<rect width="600" height="400" rx="28" fill="url(#gl{gid})"/>'
            f'<rect x="10" y="10" width="580" height="380" rx="22" fill="none" stroke="{STORE_GOLD}" stroke-opacity="0.35" stroke-width="2"/>'
            f'<circle cx="70" cy="70" r="90" fill="#ffffff" opacity="0.04"/>'
            f'<circle cx="540" cy="340" r="110" fill="#ffffff" opacity="0.03"/>'
            f'<text x="300" y="52" text-anchor="middle" font-size="19" font-weight="bold" fill="{STORE_GOLD}" '
            f'font-family="Arial, Helvetica, sans-serif" letter-spacing="6">{sub}</text>')


def _lux_brand_bar(gid, brand):
    return (f'<rect x="170" y="318" width="260" height="50" rx="25" fill="#000000" opacity="0.45" '
            f'stroke="{STORE_GOLD}" stroke-opacity="0.5"/>'
            f'<text x="300" y="351" text-anchor="middle" font-size="24" font-weight="bold" fill="{STORE_GOLD}" '
            f'font-family="Arial, Helvetica, sans-serif" letter-spacing="3">★ {brand} ★</text>')


def _store_badge(gid):
    """شارة شعار المتجر الذهبية (AS) أعلى-يسار كل صورة — صغيرة ومناسبة وثابتة."""
    return (f'<g transform="translate(24,22)">'
            f'<rect width="128" height="46" rx="14" fill="#000000" opacity="0.55" '
            f'stroke="{STORE_GOLD}" stroke-opacity="0.65" stroke-width="1.5"/>'
            f'<text x="12" y="33" font-size="26" font-weight="bold" fill="url(#gd{gid})" '
            f'font-family="Georgia, serif" font-style="italic">AS</text>'
            f'<text x="52" y="21" font-size="12" font-weight="bold" fill="{STORE_GOLD}" '
            f'font-family="Arial, Helvetica, sans-serif" letter-spacing="1.5">ARAB</text>'
            f'<text x="52" y="36" font-size="12" font-weight="bold" fill="#ffffff" '
            f'font-family="Arial, Helvetica, sans-serif" letter-spacing="1.5">STORE</text>'
            f'</g>')


def detect_brand(name):
    """يبحث أولاً عن اللعبة/البراند داخل الاسم قبل التوليد.
    يرجع (brand_en, monogram) أو (None, None) إن لم يُتعرف عليه."""
    mark = official_mark(name or "")
    if not mark:
        return None, None
    mono, _mbg, _mfg = mark
    en = to_english(name or "")
    words = en.split(" ")
    brand = " ".join(words[:2]) if len(words) > 1 else words[0]
    # إن كان الاسم يبدأ بكمية (UC/DIAMONDS...) خذ الكلمات التالية
    generic_first = {"UC", "DIAMONDS", "GOLD", "COINS", "TOP", "UP", "CARD", "CARDS",
                     "MONTHLY", "WEEKLY", "PASS", "VOUCHER", "VOUCHERS", "TICKET", "TICKETS"}
    if words and words[0] in generic_first and len(words) > 2:
        brand = " ".join(words[1:3])
    return brand, mono


def build_product_svg(name, store_name=None):
    """صورة منتج فخمة بهوية المتجر الموحدة: كحلي + توهج أحمر + ذهبي،
    العنوان إنجليزي حصراً، مع الشعار الرسمي للمنتجات المعروفة."""
    title_en = display_title(name)
    lines = [_escape_xml(ln) for ln in wrap_title(title_en, per_line=16)]
    brand = _escape_xml((store_name or STORE_MARK).strip() or STORE_MARK)
    mark = official_mark(name or "")
    gid = hashlib.md5(((name or "") + "lux").encode("utf-8")).hexdigest()[:8]
    longest = max((len(ln) for ln in lines), default=0)
    font_size = 44 if longest <= 14 else (38 if longest <= 18 else 32)
    if len(lines) == 1:
        title_svg = (f'<text x="300" y="272" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_TEXT}" font-family="Arial, Helvetica, sans-serif" letter-spacing="2" '
                     f'filter="url(#sh{gid})">{lines[0]}</text>')
    else:
        title_svg = (f'<text x="300" y="246" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_TEXT}" font-family="Arial, Helvetica, sans-serif" letter-spacing="2" '
                     f'filter="url(#sh{gid})">{lines[0]}</text>'
                     f'<text x="300" y="290" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_TEXT}" font-family="Arial, Helvetica, sans-serif" letter-spacing="2" '
                     f'filter="url(#sh{gid})">{lines[1]}</text>')
    if mark:
        mono, mbg, mfg = mark
        emblem = (f'<circle cx="300" cy="148" r="58" fill="{mbg}" filter="url(#sh{gid})"/>'
                  f'<circle cx="300" cy="148" r="58" fill="none" stroke="{STORE_GOLD}" stroke-width="3" stroke-opacity="0.85"/>'
                  f'<text x="300" y="164" text-anchor="middle" font-size="40" font-weight="bold" '
                  f'fill="{mfg}" font-family="Arial, Helvetica, sans-serif">{_escape_xml(mono)}</text>')
    else:
        emo = pick_emoji(name or "")
        emblem = (f'<circle cx="300" cy="148" r="58" fill="#161d2c" filter="url(#sh{gid})"/>'
                  f'<circle cx="300" cy="148" r="58" fill="none" stroke="{STORE_GOLD}" stroke-width="3" stroke-opacity="0.85"/>'
                  f'<text x="300" y="172" text-anchor="middle" font-size="58">{emo}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">'
            f'{_lux_defs(gid)}{_lux_frame(gid)}{_store_badge(gid)}{emblem}{title_svg}{_lux_brand_bar(gid, brand)}</svg>')


def build_section_svg(name, store_name=None):
    """صورة قسم بنفس الهوية الموحدة (عنوان إنجليزي + شعار رسمي عند توفره)."""
    title_en = display_title(name)
    lines = [_escape_xml(ln) for ln in wrap_title(title_en, per_line=16)]
    brand = _escape_xml((store_name or STORE_MARK).strip() or STORE_MARK)
    mark = official_mark(name or "")
    gid = hashlib.md5(((name or "") + "sec").encode("utf-8")).hexdigest()[:8]
    longest = max((len(ln) for ln in lines), default=0)
    font_size = 44 if longest <= 14 else (38 if longest <= 18 else 32)
    if len(lines) == 1:
        title_svg = (f'<text x="300" y="272" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_GOLD}" font-family="Arial, Helvetica, sans-serif" letter-spacing="3" '
                     f'filter="url(#sh{gid})">{lines[0]}</text>')
    else:
        title_svg = (f'<text x="300" y="246" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_GOLD}" font-family="Arial, Helvetica, sans-serif" letter-spacing="3" '
                     f'filter="url(#sh{gid})">{lines[0]}</text>'
                     f'<text x="300" y="290" text-anchor="middle" font-size="{font_size}" font-weight="bold" '
                     f'fill="{STORE_GOLD}" font-family="Arial, Helvetica, sans-serif" letter-spacing="3" '
                     f'filter="url(#sh{gid})">{lines[1]}</text>')
    if mark:
        mono, mbg, mfg = mark
        emblem = (f'<circle cx="300" cy="148" r="58" fill="{mbg}" filter="url(#sh{gid})"/>'
                  f'<circle cx="300" cy="148" r="58" fill="none" stroke="{STORE_GOLD}" stroke-width="3" stroke-opacity="0.85"/>'
                  f'<text x="300" y="164" text-anchor="middle" font-size="40" font-weight="bold" '
                  f'fill="{mfg}" font-family="Arial, Helvetica, sans-serif">{_escape_xml(mono)}</text>')
    else:
        emo = pick_emoji(name or "")
        emblem = (f'<circle cx="300" cy="148" r="58" fill="#161d2c" filter="url(#sh{gid})"/>'
                  f'<circle cx="300" cy="148" r="58" fill="none" stroke="{STORE_GOLD}" stroke-width="3" stroke-opacity="0.85"/>'
                  f'<text x="300" y="172" text-anchor="middle" font-size="58">{emo}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">'
            f'{_lux_defs(gid)}{_lux_frame(gid, "ARAB STORE • CATEGORY")}{_store_badge(gid)}{emblem}{title_svg}{_lux_brand_bar(gid, brand)}</svg>')


# ------------------------------------------------------------------
# البرومبت الدقيق الموحد (إنجليزي حصراً — يُرسل لأي API توليد خارجي)
# ------------------------------------------------------------------
STYLE_LOCK = ("luxury dark gaming store artwork, deep navy background #0b0f19, "
              "red neon glow accents #ff1a3c, gold highlights #ffc24b, "
              "small gold AS store logo badge in the top-left corner, "
              "premium glassmorphism card, soft vignette, cinematic lighting, "
              "ultra clean, centered composition, high contrast, 4k, "
              "bold uppercase English title text only, absolutely no Arabic text, "
              "no watermark")

NEGATIVE_PROMPT = ("arabic text, arabic letters, blurry text, misspelled text, "
                   "watermark, logo watermark, low quality, distorted, cluttered")


def build_precise_prompt(kind, name):
    """برومبت إنجليزي دقيق يتناسق 100% مع هوية المتجر.
    kind: product | section | subsection | category | banner.
    يُرفق وصف البراند الغني (ما هو + شعاره + دوره) ليفهمه الـ AI بدقة."""
    en = to_english(name)
    mark = official_mark(name or "")
    brand_line = (f"with official {mark[0]} brand emblem badge, " if mark
                  else "with a golden circular emblem badge containing a game icon, ")
    profile = describe_brand(name or "")
    subject_desc = describe_subject(name or "")
    context = " ".join(x for x in (profile, subject_desc) if x)
    context = f" Brand context: {context}" if context else ""
    subject = {
        "product": f"game top-up product banner for {en}",
        "section": f"game store category banner for {en}",
        "subsection": f"game store subcategory banner for {en}",
        "category": f"digital package artwork for {en}",
        "banner": f"promotional hero banner for {en}",
    }.get(kind or "product", f"game store artwork for {en}")
    return (f"{subject}.{context} {brand_line}"
            f'large centered English title "{en}", {STYLE_LOCK}')


def image_prompt_payload(kind, name):
    """يرجع (prompt_en, negative) جاهزين للإرسال لأي API خارجي."""
    return build_precise_prompt(kind, name), NEGATIVE_PROMPT


def brand_filename(name):
    return "brand-" + hashlib.md5((name or "").encode("utf-8")).hexdigest()[:12] + ".svg"


# ------------------------------------------------------------------
# ختم شعار المتجر على الصور Raster (صور API الخارجي / المرفوعة يدوياً)
# نفس تصميم شارة SVG: خلفية داكنة + إطار ذهبي + AS ذهبي + ARAB STORE
# ------------------------------------------------------------------
def _badge_font(size, serif=False):
    """خط متاح دائماً — DejaVu إن وُجد وإلا خط Pillow الافتراضي."""
    import os as _os
    candidates = []
    if serif:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    try:
        from PIL import ImageFont as _IF
        for path in candidates:
            if _os.path.isfile(path):
                try:
                    return _IF.truetype(path, size)
                except Exception:
                    continue
        try:
            return _IF.load_default(size=size)
        except TypeError:
            return _IF.load_default()
    except Exception:
        return None


def stamp_store_badge(image_bytes):
    """يختم شعار AS الذهبي أعلى-يسار الصورة. يرجع PNG bytes أو None عند أي فشل
    (مكتبة ناقصة، ملف تالف...) — المتصل يُبقي الصورة الأصلية حينها."""
    try:
        from PIL import Image as _Img, ImageDraw as _Draw
        import io as _io
    except Exception:
        return None
    try:
        if not image_bytes or len(image_bytes) > 12 * 1024 * 1024:
            return None
        img = _Img.open(_io.BytesIO(image_bytes))
        img = img.convert("RGBA")
        W, H = img.size
        if W < 120 or H < 60:
            return None  # صغيرة جداً — الختم سيغطيها
        bw, bh, mg = int(W * 0.24), int(W * 0.24 * 0.36), int(W * 0.035)
        bw, bh = max(bw, 96), max(bh, 34)
        mg = max(mg, 12)
        overlay = _Img.new("RGBA", img.size, (0, 0, 0, 0))
        dr = _Draw.Draw(overlay)
        gold = (255, 194, 75, 255)
        # خلفية الشارة
        dr.rounded_rectangle([mg, mg, mg + bw, mg + bh], radius=max(6, bh // 3),
                             fill=(0, 0, 0, 140), outline=gold,
                             width=max(2, W // 400))
        # نص AS بخط عريض مائل (تقليد الشعار الذهبي)
        fs_big = max(14, int(bh * 0.58))
        f_big = _badge_font(fs_big, serif=True) or _badge_font(fs_big)
        dr.text((mg + int(bw * 0.07), mg + int(bh * 0.08)), "AS",
                font=f_big, fill=gold)
        try:
            abb = dr.textbbox((0, 0), "AS", font=f_big)
            as_w = abb[2] - abb[0]
        except Exception:
            as_w = int(bw * 0.32)
        # ARAB STORE بخط صغير
        fs_small = max(8, int(bh * 0.26))
        f_small = _badge_font(fs_small)
        tx = mg + int(bw * 0.07) + as_w + max(4, int(bw * 0.04))
        dr.text((tx, mg + int(bh * 0.12)), "ARAB", font=f_small, fill=gold)
        dr.text((tx, mg + int(bh * 0.46)), "STORE", font=f_small, fill=(255, 255, 255, 255))
        img = _Img.alpha_composite(img, overlay).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
