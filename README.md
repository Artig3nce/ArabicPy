# الباء

الباء لغة برمجة عربية مع بيئة تطوير مكتبية، وتحوّل الكود العربي إلى Python.

## Android mode

Create a new Android file from **Android > مشروع Android جديد**. The first
supported Android syntax is:

```text
تطبيق "تطبيقي العربي"

رسالة = نص("مرحباً من الباء")
الاسم = حقل("اكتب اسمك")
زر_الترحيب = زر("اضغط هنا")

عند_النقر(زر_الترحيب):
    غيّر_النص(رسالة، "أهلاً بك في تطبيقي")
```

The IDE generates a Kivy preview and can export `main.py` and
`buildozer.spec`. APK compilation uses **WSL2 + Buildozer** and is available
from **Android > إنشاء APK عبر WSL2**.

WSL2 and Buildozer must be installed separately before APK compilation. The
current machine does not have WSL installed, but project export works without
it.
