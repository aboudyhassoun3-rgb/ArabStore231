# -*- coding: utf-8 -*-
"""تصنيف منتجات المزوّدين إلى أقسام المتجر. يرجع اسم القسم أو None (تخطّي)."""
import re

SECTIONS = [
    ("🎮 شحن الألعاب", "#7c5cff"),
    ("💳 بطاقات رقمية", "#f5a623"),
    ("🎬 اشتراكات ومنصات", "#e91e63"),
    ("🛡️ VPN وخصوصية", "#2dd4bf"),
    ("📱 حسابات وأرقام", "#4f8cff"),
    ("💬 تطبيقات الدردشة", "#a78bff"),
    ("📣 خدمات التواصل", "#22c55e"),
    ("📶 رصيد واتصالات", "#fb923c"),
    ("💵 محافظ ومدفوعات", "#eab308"),
    ("🤖 اشتراكات ذكية", "#06b6d4"),
    ("🎨 تصميم ومونتاج", "#f472b6"),
    ("📚 تعليم وكورسات", "#84cc16"),
]

# أسماء غير مفهومة تُتخطّى دائماً (تُفحص قبل كل القواعد)
SKIP_NAMES = ["سول شيل", "soul chill", "بلو 4k", "اسمر", "رواتب",
              "ليغو لايف", "gold master", "ارسيل", "آسيا سيل", "payceel",
              "ميرو", "فرامير", "لينير", "كاستمر", "ريبلت", "ريلوي",
              "أنتي جرافيتي", "ماجيك باترنز", "سوبابيس", "غيت هاب",
              "anima pack", "bloom pack", "chain pack", "flower fairy",
              "m-cash", "corite", "glimmer", "glows", "1 tag", "2 tag", "3 tag",
              "starter pack", "basic set", "common set", "advanced set",
              "random fragment", "epic weapon", "lucky bag week",
              "level up pass", "bloodstrike pre-order", "rags to riches",
              "return manual", "festive lucky", "stamp box", "phase training",
              "corridor key box",
              "limited assembly", "limited summon", "iceworld journey",
              "extreme training", "premium spiritual jade",
              "golden balls", "spatulas", "platinum",
              "breakthough", "core supporter", "initiate soul",
              "covenant", "oath of bond", "assurance of",
              "honor point", "double token lucky", "subscription perks",
              "bulletproof case", "composite case", "composition case",
              "beginner select", "handful of bucks", "stack of bucks",
              "joker cards", "cube supply", "plugin supply",
              "smugglers supply", "weaponry bundle",
              "rare augment", "rare deadly", "rare one man",
              "rare survival", "rare teamwork",
              "small queen", "small shade", "unicorn unlock",
              "epic augment core", "fortune chest", "heavy module",
              "inferno chest", "inferno equipment", "epic equipment",
              "legendary chest", "legendary equipment", "massive equipment",
              "medium equipment", "medium seasonal", "small equipment",
              "small seasonal", "blueprint vault",
              "elite augment", "huge seasonal", "large equipment",
              "large seasonal", "holy chest", "holy equipment",
              "fmp", "آور", "mena", "wish money", "ويش موني",
              "باقة 4.5", "باقة 7.58", "باقة 10$", "باقة 15.15",
              "باقة 22.73", "باقة 77.28",
              "اشتراك بريميوم", "اشتراك تصميم شهري",
              "5$ mena", "10$ mena", "20$ mena", "25$ mena",
              "35$ mena", "50$ mena", "100$ mena"]

CHAT_TOKENS = ["شات", "chat", "لايف", "live", "meyO", "mixu", "tumil", "livu",
    "hicate", "hicat", "gomeet", "bigo", "likee", "tango", "soul", "ahlan",
    "taka", "sugo", "poppo", "hago", "yoyo", "nimo", "chamet", "mico",
    "party star", "soul star", "soulfa", "moli", "faby", "nawa", "salam",
    "hiya", "kwai", "fancy", "waho", "bobo", "kiti", "sahra", "yolo",
    "yaha", "taya", "litme", "maza", "rooh", "zaar", "halla", "tayyb",
    "yudo", "yayya", "karak", "ohla", "vone", "shabab", "siya",
    "best live", "woho", "sahi", "4chat", "arab star", "crush", "hayi",
    "bulala", "falla", "wahda", "fomi", "lit chat", "sawalfna", "kafu",
    "hoki", "shila", "yobi", "dido", "vostar", "yaza", "wadi", "laka",
    "wechill", "sophia", "silla", "yula", "carni", "moma", "sohha",
    "chata", "chati", "shaghaf", "oyuni", "toki", "nita", "sami",
    "we party", "nady", "gogoc", "hi chat", "yigo", "sama", "dream",
    "westar", "lemi", "chamoji", "wasla", "lklk", "ifun", "hamster",
    "7star", "oloo", "opa live", "funni", "luyo", "yomee", "hob",
    "bota", "helili", "yaha", "ruffa", "sohi", "taj", "katchi",
    "limmatna", "yalotalk", "hebba", "wechil", "bishar", "songora",
    "nice chat", "voolaa", "hawk", "wanas", "yumi", "diwan", "fama",
    "holm", "salfa", "soffa", "go fun", "volistar", "star go", "voca",
    "wikoo", "kola", "partychill", "taif", "niko", "pocoo", "fanc",
    "hilla", "homi", "umnow", "timo", "fami", "noora", "fadaa",
    "party u", "vanoo", "kitta", "dimo", "yabi", "hoby", "hopi",
    "mekat", "pep live", "lions", "hi play", "layam", "rostar",
    "yami star", "asha", "jaco", "sodfa", "dana", "saada", "gala",
    "mango", "pocket", "fofo", "woohoo", "taala", "up fun",
    "sky chat", "mazyoun", "top voice", "pawa", "maan", "laki",
    "leesky", "lot fun", "vova", "rooka", "1star", "hati", "fun up",
    "yohoo star", "joyo", "halo star", "waaw", "lessmet", "boli",
    "yoparti", "lado", "nahki", "yoso farm", "hago", "pk star",
    "infun", "baat", "hoob", "maza", "yeeha", "vilaa", "masti",
    "dawa", "hart live", "doli live", "zaar", "e-party", "yo2",
    "yoki", "mate met", "super meet", "اومي", "hopi star", "dika",
    "siya", "best live", "sahi", "niu", "ti live", "nafass", "yena",
    "fun star", "falla", "hayuki", "amisu", "rixo", "fomi party",
    "moli star", "faby star", "7zh", "winko", "kafu", "dido live",
    "yoyo chat", "yabi chat", "habi chat", "sugo chat", "kiyo live",
    "4party", "ligo live", "dimo chat", "bobo chat", "salam chat",
    "binmo", "yooy", "fancy live", "ditto", "mr7ba", "haki",
    "bella", "wego", "super live", "habbe", "hawa", "oohla", "hapi", "هابي",
    "up live", "lami", "wyak", "saba", "aria", "nabd", "gimme",
    "allo", "yoppo", "layla", "hala me", "hami party", "hoby",
    "hi party", "mikoo", "higo live", "imu chat", "imu", "amo",
    "star mekat", "pep live", "lions chat", "hi play chat",
    "chamet", "layam", "party hero", "jaco", "sodfa chat",
    "saada chat", "gala chat", "pocket chat", "taala chat",
    "yudo chat", "sky", "mango live", "gold chat", "sahra chat",
    "laki chat", "vova chat", "rooka", "hayi", "hati", "fun up",
    "yhoo", "joyo live", "halo", "waaw chat", "boli chat",
    "lado chat", "nahki chat", "hago", "inFun", "baat", "hoob",
    "maza", "masti chat", "rooh chat", "zaar chat", "halla chat",
    "yo2 app", "yoki chat", "mate", "tayyb chat", "اومي",
    "yayya", "karak chat", "vone", "siya chat", "sahi",
    "4chat", "crush live", "niu chat", "fun star", "top top",
    "hayuki", "fomi", "litme", "moli", "faby", "winko live",
    "hoki", "shila", "yobi chat", "dido chat", "yaza chat",
    "wadi", "laka", "sophia", "yula", "carni live", "sohha",
    "shaghaf", "toki voice", "we party", "gogoc", "yigo chat",
    "nimo tv", "sama chat", "dream chat", "westar", "lemi live",
    "chamoji", "lklk", "hamster", "oloo", "funni", "luyo",
    "yomee", "bota chat", "helili", "yaha chat", "sohi chat",
    "taj star", "katchi", "hebba", "bishar chat", "songora",
    "nice", "hawk", "wanas", "diwan talk", "fama", "holm",
    "salfa", "soffa", "volistar", "voca chat", "wikoo",
    "kola party", "taif star", "pocoo chat", "hilla", "homi",
    "tim o", "timo club", "fami", "noora live", "fadaa live",
    "vanoo", "kitta"]


_re_cache = {}

def _norm_ar(s):
    return (s or "").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")


def _hit(k, low):
    """مطابقة بكلمة كاملة (حدود كلمات) لمنع الالتباس مثل بيا داخل كولومبيا."""
    t = _norm_ar((k or "").lower())
    if not t:
        return False
    rx = _re_cache.get(t)
    if rx is None:
        try:
            rx = re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)")
        except Exception:
            return t in low
        _re_cache[t] = rx
    try:
        return rx.search(low) is not None
    except Exception:
        return t in low


def classify(name, price=0):
    """يرجع اسم القسم أو None للتخطي."""
    if not name or not str(name).strip():
        return None
    try:
        p = float(price or 0)
    except Exception:
        p = 0
    if p <= 0 or p > 10000:
        return None
    n = str(name).strip()
    low = n.lower()
    low = re.sub("(?<!\\w)\\u0627\\u0644(?=[\\u0600-\\u06FF])", "", _norm_ar(low))
    compact = re.sub(r"\s+", " ", n)
    if re.fullmatch(r"[\d\s,.$+×x\-/]+", compact):
        return None
    for s in SKIP_NAMES:
        if s and _hit(s, low):
            return None
    if re.match(r"^\d+\s*يوم", n):
        return None
    if re.match(r"^باقة\s+[\d.$]+", n):
        return None

    smm = ["متابعين", "مشتركين", "مشاهدات", "لايكات", "followers",
           "likes", "views", "subscribers", "members", "أعضاء", "تصويت",
           "تفاعل"]
    if any(_hit(k, low) for k in smm):
        return "📣 خدمات التواصل"
    streaming = ["netflix", "نتفلكس", "shahid", "شاهد", "prime video",
                 "برايم فيديو", "disney", "ديزني", "watch tv", "ووتش تي في",
                 "ووتش", "osn", "او اس ان", "crunchy", "كرانشي", "anghami",
                 "انغامي", "deezer", "ديزر", "youtube", "يوتيوب", "spotify",
                 "سبوتفاي", "تود", "tod", "لوك ", "شامنا", "ايبي تي في",
                 "ايبي", "زين تي في", "ابل تي في", "apple tv",
                 "snapchat plus", "سناب شات بلس", "تلغرام مميز",
                 "telegram premium"]
    if any(_hit(k, low) for k in streaming):
        return "🎬 اشتراكات ومنصات"
    vpn = ["express", "اكسبريس", "nord", "نورد", "surf", "سيرف شارك",
           "proton", "بروتون", "windscribe", "وايندسكرايب", "hotspot",
           "هوت سبوت", "pure", "بيور", "pia", "بيا", "cyber ghost",
           "سايبر غوست", "kaspersky", "كاسبرسكي", "avira", "آفيرا", "vpn",
           "gearup", "جير اب"]
    if any(_hit(k, low) for k in vpn):
        return "🛡️ VPN وخصوصية"
    ai = ["chatgpt", "شات جي بي تي", "gpt", "gemini", "جيمني", "claude",
          "كلود", "grok", "غروك", "سوبر غروك", "perplexity", "بيربليكسيتي",
          "elevenlabs", "إليفين", "leonardo", "ليوناردو", "suno", "سونو",
          "heygen", "هيجن", "kling", "كلينج", "kimi", "كيمي", "cursor",
          "كورسور", "n8n", "ان ايت ان", "quillbot", "كويل", "غاما",
          "gamma"]
    if any(_hit(k, low) for k in ai):
        return "🤖 اشتراكات ذكية"
    design = ["canva", "كانفا", "adobe", "ادوبي", "capcut", "كاب كات",
              "picsart", "بيكس ارت", "envato", "إنفاتو", "invideo",
              "ان فيديو", "remini", "ريميني", "faceapp", "فيس اب",
              "flaticon", "فلات ايكون", "ilovepdf", "آي لوف",
              "miro", "ميرو"]
    if n.startswith("تصميم"):
        return "🎨 تصميم ومونتاج"
    if any(_hit(k, low) for k in design):
        return "🎨 تصميم ومونتاج"
    edu = ["udemy", "يودمي", "coursera", "كورسيرا", "duolingo", "دولينجو"]
    if any(_hit(k, low) for k in edu):
        return "📚 تعليم وكورسات"
    pay = ["visa", "فيزا", "usdt", "binance", "بينانس", "paypal",
           "باي بال", "wise", "western", "ويسترن", "payoneer", "بايونير",
           "revolut", "perfect mon", "بيرفكت", "shamcash", "شام كاش",
           "papara", "mtn", "syriatel"]
    # mtn/syriatel تذهب للرصيد — نميّزها لاحقاً
    if any(k in n or k in low for k in ["visa", "فيزا", "usdt", "binance",
                                        "بينانس", "paypal", "باي بال", "wise",
                                        "western", "ويسترن", "payoneer",
                                        "بايونير", "revolut", "perfect mon",
                                        "بيرفكت", "papara"]):
        return "💵 محافظ ومدفوعات"
    accounts = ["gmail", "جيميل", "apple id", "ابل", "facebook", "فيسبوك",
                "icloud", "ايكلاود", "outlook", "اوتلوك", "instagram",
                "انستجرام", "tiktok", "تيك توك", "snapchat", "سناب شات",
                "imo", "wechat", "twitter", "whatsapp", "واتساب",
                "telegram - يدوي", "يدوي", "حساب "]
    if any(_hit(k, low) for k in accounts):
        return "📱 حسابات وأرقام"
    if re.search(r"(?<!\d)\+\d{2,}", n):
        return "📱 حسابات وأرقام"
    if any(_hit(k, low) for k in CHAT_TOKENS):
        return "💬 تطبيقات الدردشة"
    if re.search(r"عملة\s*-|coins?\s*-", low):
        return "💬 تطبيقات الدردشة"
    # الرصيد (سيريتل/MTN) قبل البطاقات
    if "mtn" in low or "syriatel" in low or "سيريتل" in n or "شام كاش" in n or "shamcash" in low:
        return "📶 رصيد واتصالات"
    if "ليرة" in n:
        return "📶 رصيد واتصالات"
    games = ["honkai", "هونكاي", "jades", "onmyoji", "onmyoij",
             "valorant", "فالورانت", "fifa", "فيفا", "efootball",
             "fortnite", "فورتنايت", "pubg", "ببجي", "free fire",
             "فري فاير", "blood strike", "بلود سترايك", "farlight",
             "فارلايت", "mobile legends", "موبايل ليجند", "genshin",
             "جينشن", "غينشن", "overwatch", "اوفرواتش", "call of duty", "ludo", "لودو", "marvel", "مارفل", "jawaker",
             "جواكر", "8ball", "8 ball", "بلياردو", "diamonds",
             "جوهرة", "جواهر", "ذهب", "دهب", "gold", "coins", "coin", "كوينز",
             "عملة", "عملات", "gems", "gem", "شدات", "شدة", "vouchers", "voucher", "قسائم",
             "قسيمة", "tickets", "ticket", "تذاكر", "تذكرة", "pass", "باس",
             "باص", "عضوية", "عضويات", "credits", "credit", "نقاط الشحن", "shards",
             "شظايا", "bundles", "bundle", "chest", "packs", "pack", "ingots",
             "opals", "أوبال", "quartz", "كرستال", "بلورة",
             "coupon", "كوبون", "كوبونات", "tokens", "token", "keys",
             "cp", "vp", "rp", "nc", "g-coin",
             "uc", "bonds", "maplem", "nikke", "monochrome", "gcube",
             "stone", "costume", "box", "cash", "module",
             "honor", "oxide", "zepeto", "wild cores",
             "super sus", "monthly card", "weekly card",
             "fc points", "silver",
             "mortal", "mongil", "speed", "idol", "legacy",
             "rivals", "isekai", "farlight84"]
    if any(_hit(k, low) for k in games):
        return "🎮 شحن الألعاب"
    cards = ["itunes", "ايتونز", "google play", "غوغل بلاي", "playstation",
             "بلاي ستيشن", "psn", "xbox", "اكس بوكس", "steam", "ستيم",
             "amazon", "امازون", "razer", "ريزر", "roblox", "روبلوكس",
             "نجوم تلغرام", "telegram stars"]
    if any(_hit(k, low) for k in cards):
        return "💳 بطاقات رقمية"
    return None


def section_color(name):
    for s, c in SECTIONS:
        if s == name:
            return c
    return "#7c5cff"


# كلمات تُحذف من أطراف الاسم عند استخراج اسم اللعبة/المنتج الأساسي
_GAME_STRIP = {
    "v", "vp", "uc", "nc", "gold", "golds", "silver", "diamonds", "diamond",
    "jades", "jade", "coins", "coin", "gems", "gem", "shards", "shard",
    "crystals", "crystal", "vouchers", "voucher", "tickets", "ticket",
    "bonds", "ingots", "keys", "bucks", "chips", "credits", "credit",
    "opals", "opal", "quartz", "points", "pass", "membership", "card",
    "bundle", "chest", "pack", "fund", "module", "supply", "cube", "orb",
    "token", "tokens", "code", "set", "plus", "premium", "monthly",
    "weekly", "coupon", "coupons", "games", "لعبة", "stone", "ستون",
    "bonus", "بونص", "cp", "rp", "usa", "uk", "uae", "ksa",
    "cm", "sg", "my", "ph", "vn", "tr",
    "eu", "us", "mea", "mena", "sar", "aed", "cad", "tl", "try", "usd",
    "eur", "global", "of", "the", "a", "على", "جوهرة", "جواهر", "ذهب",
    "دهب", "عملة", "عملات", "ماس", "ماسة", "شدة", "شدات", "قسيمة",
    "قسائم", "تذكرة", "تذاكر", "كوبون", "كوبونات", "بلورة", "كرستال",
    "رصيد", "شحن", "باقة", "الباقة", "بطاقة", "ليرة", "ريال", "دولار",
    "شهر", "شهرية", "شهور", "سنة", "سنوات", "يوم", "ايام", "عضوية",
    "كود", "حزمة",
}

_GAME_REGION = {
    "امريكي", "أمريكي", "اوربي", "أوروبي", "أوروبا", "usa", "امريكا",
    "تركيا", "tr", "عربي", "عربية", "أجنبية", "أجنبي", "بريطانيا",
    "فرنسي", "كندي", "سعودي", "الماني", "لبناني", "اماراتي",
}


def extract_game(name):
    """يستخرج اسم اللعبة/المنتج الأساسي (لقسم مستقل لكل منتج).
    يرجع '' إذا تعذّر الاستخراج."""
    n = str(name or "").strip()
    if not n:
        return ""
    n = re.split(r"\s*[|｜]\s*", n)[0]
    if " - " in n:
        n = n.split(" - ")[0]
    toks = [t for t in re.split(r"\s+", n) if t and not re.search(r"\d", t)]
    toks = [t for t in toks if len(t) > 1 and not re.fullmatch(r"[^\w\u0600-\u06FF]+", t)]

    def _skey(t):
        t = _norm_ar(t.lower())
        t = re.sub("^(ال|لل|ب|ل)(?=[\u0600-\u06FF])", "", t)
        return t

    while toks and _skey(toks[-1]) in _GAME_STRIP:
        toks.pop()
    while toks and _skey(toks[0]) in _GAME_STRIP:
        toks.pop(0)
    toks = [t for t in toks if t not in _GAME_REGION]
    game = " ".join(toks).strip()
    if len(game) < 2:
        return ""
    if all(_skey(t) in _GAME_STRIP for t in game.split()):
        return ""
    return game


def game_style(name):
    """إيموجي ولون مميز لقسم اللعبة."""
    try:
        from branding import pick_emoji, PALETTES
    except Exception:
        return "🎮", "#7c5cff"
    import hashlib as _hl
    emo = pick_emoji(name or "")
    h = int(_hl.md5((name or "").encode("utf-8")).hexdigest(), 16)
    return emo, PALETTES[h % len(PALETTES)][0]
