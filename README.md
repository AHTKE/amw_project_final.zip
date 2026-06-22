# AMW Streaming Proxy — Vercel Deployment

## 1) Generate session string (one time, on your computer)

```bash
pip install telethon
python generate_session.py
```

أدخل `API_ID` و `API_HASH`، رقم تليفونك، وكود تليجرام. هتطلع لك سلسلة طويلة — انسخها.

## 2) Deploy to Vercel

1. ارفع المجلد ده على GitHub.
2. في Vercel: **New Project → Import** الريبو.
3. **Framework Preset:** Other (Vercel هيكتشف Python تلقائياً من `requirements.txt`).
4. في **Settings → Environment Variables** أضف:
   - `TELEGRAM_API_ID` = الـ API ID
   - `TELEGRAM_API_HASH` = الـ API Hash
   - `TELEGRAM_SESSION` = السلسلة من الخطوة 1
5. اضغط **Deploy**.

## 3) Test

```
https://<your-project>.vercel.app/health
https://<your-project>.vercel.app/stream?channel_id=123456789&message_id=42
```

## 4) في موقع Lovable

سرّ `PROXY_BASE_URL` معمول بالفعل ومضبوط على:
`https://amw-project-final-zip.vercel.app`

غيّره لو الـ URL مختلف.

## ⚠️ حدود Vercel Free

- **مدة التنفيذ:** 60 ثانية لكل request → الكود بيقسم البث 8MB لكل request، والمتصفح يطلب الجزء التالي بـ Range.
- **Bandwidth:** 100 GB/شهر → فيديوهات كتيرة هتاكل ده بسرعة.
- **لا يوجد:** فايل سيستم للكتابة، لذلك الـ session لازم يكون String في env.
