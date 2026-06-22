# AMW Project

## تشغيل محلي
```bash
pip install -r requirements.txt
python main.py
```

## متغيرات البيئة
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION` (StringSession هو الأفضل على Vercel)
- `TELEGRAM_SESSION_FILE` (افتراضي: `amw_new_session.session`)

## ملاحظات مهمة لـ Vercel
- Vercel Functions لها حد لمدة التنفيذ، لذلك لا يمكن الاعتماد عليها لبث غير محدود.
- نظام الملفات داخل Vercel للوظيفة يكون للقراءة فقط، مع مساحة كتابة مؤقتة داخل `/tmp`.
- لهذا السبب تم تعديل المشروع لنسخ ملف الجلسة إلى `/tmp` عند الحاجة، أو استخدام `TELEGRAM_SESSION` مباشرة.
- هذا المشروع يقلل استهلاك الذاكرة ويحسن البث، لكن لا يمكن جعله "صفر استهلاك" على Vercel طالما أن الفيديو يمر عبر الوظيفة نفسها إلى المتصفح.

## أفضل إعداد عملي
إذا كان هدفك تشغيل الفيديو بسرعة مع أقل ضغط ممكن:
1. استخدم `TELEGRAM_SESSION` كـ StringSession.
2. ارفع الفيديوهات بحجم معقول.
3. اجعل الواجهة تطلب `Range` افتراضيًا.
4. اختبر التشغيل على Vercel على فيديوهات قصيرة أولًا.
