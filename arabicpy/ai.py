"""Small, offline AI-style helper available to every ArabicPy program."""


def reply(question):
    """Return a friendly Arabic response for a short prompt."""
    text = str(question).strip()
    normalized = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").lower()

    if not text:
        return "اكتب سؤالاً بعد اسأل، وسأحاول مساعدتك."
    if any(word in normalized for word in ("مرحبا", "اهلا", "السلام")):
        return "مرحباً! أنا مساعد ArabicPy البسيط. كيف يمكنني مساعدتك؟"
    if "arabicpy" in normalized or "عربي باي" in normalized:
        return "ArabicPy لغة برمجة عربية تُحوّل برنامجك إلى Python ثم تشغّله."
    if any(word in normalized for word in ("اسمك", "من انت")):
        return "أنا مساعد صغير مدمج في ArabicPy، وأعمل محلياً دون اتصال بالإنترنت."
    if "كيف" in normalized:
        return "ابدأ بخطوات صغيرة، واكتب برنامجك ثم اضغط تشغيل."
    return f"فهمت سؤالك: {text}\nهذه النسخة التجريبية تعمل محلياً، وسنضيف لها نموذج ذكاء أكبر لاحقاً."
