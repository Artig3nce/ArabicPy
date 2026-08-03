"""Local AI integration for AlBaa through Ollama."""

import json
import urllib.error
import urllib.request

from .rag import context_for


DEFAULT_MODEL = "qwen3:8b"
SYSTEM_PROMPT = (
    "أنت مساعد الباء، مساعد ذكي يتحدث العربية بوضوح. "
    "مهمتك الأساسية هي مساعدة المستخدم في كتابة وشرح وتصحيح كود لغة الباء العربية، "
    "لكنك تجيب أيضاً عن أي سؤال آخر يطرحه المستخدم، بما في ذلك الأسئلة عن المستندات "
    "التي رفعها إلى معرفة RAG. أجب دائماً عن السؤال الفعلي الذي طرحه المستخدم أولاً؛ "
    "لا تتجاهل سؤاله وتتحول للحديث عن الكود المرفق إلا إذا كان سؤاله عن الكود فعلاً. "
    "إذا لم تعرف صيغة من لغة الباء، صرّح بذلك ولا تخترع أمراً غير موجود."
)


def reply(question, model=DEFAULT_MODEL, timeout=300):
    """Return a local Ollama response for the Arabic `اسأل(...)` command."""
    text = str(question).strip()
    if not text:
        return "اكتب سؤالاً بعد اسأل، وسأحاول مساعدتك."
    payload = json.dumps({
        "model": model,
        "prompt": (
            f"/no_think\n{SYSTEM_PROMPT}\n\n"
            f"معرفة موثقة مسترجعة من قاعدة الباء:\n{context_for(text)}\n\n"
            f"سؤال المستخدم:\n{text}"
        ),
        "stream": False,
        "think": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("response", "").strip() or "لم يُرجع النموذج إجابة."
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return f"النموذج {model} غير مثبت. ثبّته بالأمر: ollama pull {model}"
        return f"تعذر تشغيل النموذج المحلي: HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "تعذر الاتصال بـ Ollama. شغّل Ollama ثم حاول مجدداً."
