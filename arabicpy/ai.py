"""Small offline helper available to programs written in الباء."""


def reply(question):
    """Return a friendly Arabic response for a short prompt."""
    text = str(question).strip()
    normalized = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").lower()

    if not text:
        return "اكتب سؤالاً بعد اسأل، وسأحاول مساعدتك."
    if any(word in normalized for word in ("مرحبا", "اهلا", "السلام")):
        return "مرحباً! أنا مساعد الباء البسيط. كيف يمكنني مساعدتك؟"
    if "الباء" in normalized:
        return "الباء لغة برمجة عربية تُحوّل برنامجك إلى Python ثم تشغّله."
    if any(word in normalized for word in ("اسمك", "من انت")):
        return "أنا مساعد صغير مدمج في الباء، وأعمل محلياً دون اتصال بالإنترنت."
    if "كيف" in normalized:
        return "ابدأ بخطوات صغيرة، واكتب برنامجك ثم اضغط تشغيل."
    return f"فهمت سؤالك: {text}\nهذه النسخة التجريبية تعمل محلياً، وسنضيف لها نموذج ذكاء أكبر لاحقاً."
