# ArabStore231

<!-- omgithub:readme:start -->
## 🚀 Build, play, and remix with OMGithub

**Remixed using [OMGithub.com](https://omgithub.com).**

[![OMGithub](https://img.shields.io/badge/OMGithub-Open%20project-orange?style=for-the-badge)](https://omgithub.com/aboudyhassoun3-rgb/ArabStore231)
[![GitHub](https://img.shields.io/badge/GitHub-Source-181717?logo=github&style=for-the-badge)](https://github.com/aboudyhassoun3-rgb/ArabStore231)

- 🎮 [Open the project](https://omgithub.com/aboudyhassoun3-rgb/ArabStore231).
- ✨ [Remix this project](https://omgithub.com/?remix=aboudyhassoun3-rgb%2FArabStore231).
- 💻 [Explore the source](https://github.com/aboudyhassoun3-rgb/ArabStore231).
- 🛠️ [Check build runs](https://github.com/aboudyhassoun3-rgb/ArabStore231/actions).
- 🐛 [Report an issue](https://github.com/aboudyhassoun3-rgb/ArabStore231/issues).
- 👤 [Explore the creator's projects](https://omgithub.com/aboudyhassoun3-rgb).
- 🌍 [Create with OMGithub](https://omgithub.com).
- 🧬 [Explore the remix source](https://github.com/aboudyhassoun3-rgb/ArabStore231).
<!-- omgithub:readme:end -->

## 🛍️ ARAB STORE — نفس تصميم النسخة الأصلية طبق الأصل

الواجهة مطابقة تماماً للملف الأصلي (شاشة البداية المتحركة، القائمة الجانبية،
كرة الدعم الواحدة القابلة للفتح، الثيم الكحلي + الأحمر المتوهج، عربي/EN، ليلي)،
مع توقيع «برمجة وتصميم @aboudy2312» وعلامة تيليجرام، وكل المميزات كاملة بدون نقصان.

### 📁 البنية

```
app.py              ← الباكند (Flask + SQLite محلياً / Postgres على Vercel)
api/index.py        ← نقطة دخول Vercel (تستورد app)
public/             ← واجهة الأصلي طبق الأصل + كل الصفحات والأصول
vercel.json         ← إعداد النشر على Vercel (تحويل كل الطلبات لـ Flask)
requirements.txt    ← اعتماديات بايثون
.env.example        ← متغيرات البيئة
```

### 💻 تشغيل محلي

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000/store.html
# دخول الأدمن: admin564
```

### ☁️ النشر على Vercel

1. ارفع المشروع إلى GitHub ثم استورده في Vercel (بدون تعديل أي إعداد — يكتشف كل شيء تلقائياً).
2. (اختياري لكن يُنصح به) أضف متغيرات البيئة في Vercel → Settings → Environment Variables:
   - `ARAB_SECRET_KEY` (قيمة عشوائية طويلة — لجلسات ثابتة، وإلا يعمل الموقع بمفتاح مؤقت)
   - `ARAB_ADMIN_PASSWORD` (افتراضي: `admin564`)
   - `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (لصور دائمة)
   - `ARAB_API_TOKEN` + `ARAB_API_BASE_URL` (مزوّد الشحن — اختياري)
   - `ARAB_VAPID_*` (إشعارات الخلفية — اختياري)
3. Deploy. ثم تحقق: `https://YOUR-APP.vercel.app/health` يجب أن يرجع `{"ok":true}`.

### 💾 حفظ البيانات نهائياً (مهم — وإلا تُمسح البيانات!)

بدون الخطوات التالية يعمل المتجر على تخزين مؤقت يُمسح مع كل نشر:
1. افتح **supabase.com** وأنشئ حساباً ومشروعاً جديداً (مجاني).
2. من لوحة المشروع: **Connect** ← انسخ رابط **Pooler** (المنفذ 6543) وضع كلمة مرور قاعدة البيانات فيه.
3. في Vercel أضف متغير `DATABASE_URL` بهذا الرابط وأعد النشر.
4. تحقق من `https://YOUR-APP.vercel.app/health` — يجب أن يظهر `"storage":"persistent-postgres"`.

> تسجيل الدخول يعمل على كل النسخ تلقائياً بدون أي إعداد (الجلسات محفوظة في قاعدة البيانات).

#### 🛠️ ظهر لك 404 NOT_FOUND؟

- تأكد أنك نشرت **آخر نسخة** من الكود (Vercel → Deployments → أعد النشر Redeploy إن لزم).
- تأكد من ضبط `ARAB_SECRET_KEY` ثم أعد النشر.
- افتح صفحة `/health` أولاً: إن عملت فالمشكلة في رابط الصفحة فقط، والرئيسية على `/store.html`.

### ✨ المميزات (كاملة مثل الأصلي وأكثر)

- تسجيل/دخول + استعادة كلمة المرور بكود + حظر + عملة USD/SYP + لغة AR/EN + ثيم
- أقسام رئيسية وفرعية، منتجات وباقات (مخزون، حد كمية، يتطلب ID، صور رفع)
- محفظة + إيداع تلقائي/يدوي/فواتير + طلبات فورية + تحديث حالة
- إحالة وأرباح، نشاط، إشعارات داخل الموقع + WebPush
- API تجار `ALSH-` و`client/api` متوافق + توثيق + كتالوج public_id
- لوحة أدمن: إحصائيات وأرباح وتنبيهات، طلبات متجر (قبول/رفض/تنفيذ)، إيداعات،
  مستخدمون (رصيد/حظر/خصم/API)، خصومات VIP، كتالوج كامل، استيراد CSV وتراجع،
  مزوّدون وربط واستيراد، طرق إيداع، بنرات وشعارات **رفع صور**، صيانة، مشرفون،
  نسخ احتياطي واستعادة ومسح، صورة AI
