"""Bilingual UI strings for the Al-Baa IDE.

`TRANSLATIONS` maps an English string (or a `.format()`-style template written
in English) to its Arabic counterpart. `ArabicPyIDE.t()` looks a string up in
this table when the active UI language is Arabic, and returns the English
text unchanged otherwise -- so the English text doubles as both the runtime
default and the dictionary key.
"""

LANGUAGE_NAMES = {"en": "English", "ar": "العربية"}

TRANSLATIONS = {
    # -- Title bar --
    "Arabic Programming Language": "لغة البرمجة العربية",

    # -- Menu bar --
    "File": "ملف",
    "New File": "ملف جديد",
    "Open File...": "فتح ملف...",
    "Save": "حفظ",
    "Refresh Explorer": "تحديث المستكشف",
    "New Android Project": "مشروع تطبيق جديد",
    "New PySide6 Project...": "مشروع PySide6 جديد...",
    "New PySide6 Project": "مشروع PySide6 جديد",
    "Project name:": "اسم المشروع:",
    "Choose a Location for the New Project": "اختر مكان حفظ المشروع الجديد",
    "Folder Already Exists": "المجلد موجود بالفعل",
    'A folder named "{name}" already exists there.': 'يوجد بالفعل مجلد باسم "{name}" في هذا الموقع.',
    "Project Creation Failed": "فشل إنشاء المشروع",
    "Export Cross-Platform Project...": "تصدير مشروع لكل المنصات...",
    "Edit": "تحرير",
    "Undo": "تراجع",
    "Redo": "إعادة",
    "Cut": "قص",
    "Copy": "نسخ",
    "Paste": "لصق",
    "Select": "تحديد",
    "Select All": "تحديد الكل",
    "Find...": "بحث...",
    "View": "عرض",
    "Toggle Explorer": "إظهار / إخفاء المستكشف",
    "Toggle Output": "إظهار / إخفاء المخرجات",
    "Toggle Python Code": "إظهار / إخفاء كود Python",
    "Run": "تشغيل",
    "Run Program": "تشغيل البرنامج",
    "Clear Output": "مسح المخرجات",
    "Setup GitHub": "إعداد GitHub",
    "Push App to GitHub": "رفع التطبيق إلى GitHub",
    "Build APK via GitHub": "إنشاء APK عبر GitHub",
    "Build iOS App via GitHub": "إنشاء تطبيق iOS عبر GitHub",
    "Android": "Android",
    "Export Android Project...": "تصدير مشروع Android...",
    "Install APK Tools": "تثبيت أدوات APK",
    "Build APK": "إنشاء APK",
    "Help": "تعليمات",
    "About Al-Baa": "حول الباء",

    # -- Toolbar --
    "＋ New": "＋ جديد",
    "Open": "فتح",
    "↶ Undo": "↶ تراجع",
    "Undo (Ctrl+Z)": "تراجع (Ctrl+Z)",
    "↷ Redo": "↷ إعادة",
    "Redo (Ctrl+Y or Ctrl+Shift+Z)": "إعادة (Ctrl+Y أو Ctrl+Shift+Z)",
    "⌕ Find": "⌕ بحث",
    "✦ AI Assistant": "✦ مساعد ذكي",
    "AI Network": "شبكة AI",
    "Stop AI Network": "إيقاف شبكة AI",
    "Remote AI": "AI بعيد",
    "Use an Al-Baa model running on another computer": "استخدام نموذج الباء الموجود على كمبيوتر آخر",
    "Remote AI ✓": "AI بعيد ✓",
    "RAG Documents": "مستندات RAG",
    "Show Python Code": "إظهار كود Python",
    "Hide Python Code": "إخفاء كود Python",
    "Cancel": "إلغاء",
    "☀ Theme": "☀ المظهر",
    "☾ Theme": "☾ المظهر",
    "Toggle Al-Baa's overall theme": "تبديل مظهر الباء بالكامل",
    "↑ Push to GitHub": "↑ رفع إلى GitHub",
    "▣ Build APK": "▣ إنشاء APK",
    "Build an APK in the cloud via GitHub Actions": "إنشاء APK سحابيًا عبر GitHub Actions",
    "▣ Build iOS": "▣ إنشاء iOS",
    "Build an iOS Simulator app in the cloud on macOS via GitHub Actions": "إنشاء تطبيق iOS Simulator سحابيًا على macOS عبر GitHub Actions",
    "▣ Cross-Platform Bundle": "▣ حزم المنصات",
    "Generate a project for Browser, Windows, Linux, macOS, Android, and iOS": "توليد مشروع للمتصفح وWindows وLinux وmacOS وAndroid وiOS",
    "Designer": "تصميم",

    # -- Activity bar / sidebar / tabs / find bar --
    "EXPLORER": "المستكشف",
    "⌄  My Projects": "⌄  مشاريعي",
    "Untitled.apy": "غير محفوظ.apy",
    "Al-Baa — Arabic Code": "الباء — الكود العربي",
    "Search in file…": "ابحث في الملف…",
    "Next result (Enter)": "النتيجة التالية (Enter)",
    "Close (Escape)": "إغلاق (Escape)",
    "Python Code": "كود بايثون",

    # -- Output panel / status bar --
    "OUTPUT": "المخرجات",
    "TERMINAL": "الطرفية",
    "[Terminal session ended. Type a command to start a new one.]":
        "[انتهت جلسة الطرفية. اكتب أمراً لبدء جلسة جديدة.]",
    "Ready to run.": "جاهز للتشغيل.",
    "Autosave enabled": "الحفظ التلقائي مفعّل",
    "Line 1, Column 1": "السطر 1، العمود 1",
    "UTF-8     Arabic": "UTF-8     العربية",
    "Waiting to autosave…": "بانتظار الحفظ التلقائي…",
    "Save the file once to enable autosave": "احفظ الملف أول مرة لتفعيل الحفظ التلقائي",
    "Autosaved": "تم الحفظ تلقائيًا",
    "Autosave failed": "تعذر الحفظ التلقائي",
    "Line {line}, Column {column}": "السطر {line}، العمود {column}",
    "Close": "إغلاق",
    "Rename File": "تغيير اسم الملف",
    "New name:": "الاسم الجديد:",
    "Invalid Name": "اسم غير صالح",
    "Enter a filename only, without a path or disallowed characters.": "اكتب اسم ملف فقط بدون مسار أو رموز غير مسموحة.",
    "Name In Use": "الاسم مستخدم",
    "A file with this name already exists.": "يوجد ملف بهذا الاسم بالفعل.",
    "Could Not Rename": "تعذر تغيير الاسم",
    "# Write Al-Baa code on the left\n# The generated Python code will appear here.":
        "# اكتب كود الباء في الجهة اليمنى\n# The generated Python code will appear here.",

    # -- AI chat panel --
    "Al-Baa Assistant": "مساعد الباء",
    "Connected": "متصل الآن",
    "Model:": "النموذج:",
    "Choose an Ollama model for this device, or type its name": "اختر نموذج Ollama لهذا الجهاز أو اكتب اسمه",
    "Al-Baa Assistant is thinking": "مساعد الباء يفكر",
    "{base} ({count} queued)": "{base} ({count} في الانتظار)",
    "Type your message...": "اكتب رسالتك هنا...",
    "Enter to send — Shift+Enter for a new line": "Enter للإرسال — Shift+Enter لسطر جديد",
    "Add a document to the RAG knowledge base": "إضافة مستند إلى معرفة RAG",
    "Send": "إرسال",
    "Stop": "إيقاف",
    "☀ Theme": "☀ المظهر",
    "☾ Theme": "☾ المظهر",

    # -- RAG library page --
    "RAG Knowledge Library": "مكتبة معرفة RAG",
    "+ Add Documents": "+ إضافة مستندات",
    "Delete Selected": "حذف المحدد",
    "No documents added yet.\nClick \"+ Add Documents\" to start building your RAG knowledge base.":
        "لم تتم إضافة أي مستندات بعد.\nاضغط \"+ إضافة مستندات\" لبدء بناء معرفة RAG.",
    "{count} document(s)": "{count} مستند",
    "  ◇  {name}      {size} KB": "  ◇  {name}      {size} كيلوبايت",
    "Delete Document": "حذف مستند",
    "Delete \"{name}\" from the RAG knowledge base?": "هل تريد حذف \"{name}\" من معرفة RAG؟",
    "Add Documents to RAG Knowledge Base": "إضافة مستندات إلى معرفة RAG",
    "Supported Documents (*.txt *.md *.apy *.py *.json *.csv *.pdf *.docx)":
        "المستندات المدعومة (*.txt *.md *.apy *.py *.json *.csv *.pdf *.docx)",
    "Extracting and indexing documents...": "بدأ استخراج وفهرسة المستندات...",
    "Extracting and indexing:\n{filename}\n\nProgress: {value}%\nOCR may take a while the first time it's used.":
        "جارٍ استخراج وفهرسة:\n{filename}\n\nالتقدم: {value}%\nقد يستغرق OCR بعض الوقت في أول استخدام.",
    "Added {count} document(s) to the RAG library.": "تمت إضافة {count} مستند إلى مكتبة RAG.",
    "Could not add:": "تعذر إضافة:",

    # -- AI backend --
    "AI Assistant": "المساعد الذكي",
    "Wait until the assistant finishes its current answer.": "انتظر حتى ينتهي المساعد من الإجابة الحالية.",
    "Could not start a connection to the local AI engine.": "تعذر بدء الاتصال بمحرك الذكاء المحلي.",
    "Could Not Start AI Network": "تعذر تشغيل شبكة AI",
    "Could not open port 8765 on this device:\n{error}": "تعذر فتح المنفذ 8765 على هذا الجهاز:\n{error}",
    "Stop AI Network": "إيقاف شبكة AI",
    "The AI server is running on this computer.\n\n"
    "Address: {address}\n"
    "Access token: {token}\n\n"
    "To use it from work: install Tailscale on both devices, sign in with the same account, "
    "then use this computer's name or Tailscale address with port 8765.\n"
    "Example: http://computer-name:8765\n\n"
    "If a Windows Firewall prompt appears, only allow access on private networks.":
        "خادم الذكاء يعمل على هذا الكمبيوتر.\n\n"
        "العنوان: {address}\n"
        "رمز الوصول: {token}\n\n"
        "للاستخدام من العمل: ثبّت Tailscale على الجهازين، وسجّل الدخول بالحساب نفسه، "
        "ثم استخدم اسم هذا الكمبيوتر أو عنوان Tailscale مع المنفذ 8765.\n"
        "مثال: http://اسم-الكمبيوتر:8765\n\n"
        "إذا ظهرت نافذة جدار حماية Windows فاسمح بالوصول للشبكات الخاصة فقط.",
    "AI Server Not Found": "خادم AI غير موجود",
    "AlBaaAIHost.exe wasn't found inside the Al-Baa package.": "ملف AlBaaAIHost.exe غير موجود داخل حزمة الباء.",
    "Could not start the AI server in the background.": "تعذر بدء خادم AI في الخلفية.",
    "The AI server is running in the background and will start automatically with Windows.\n\n"
    "Local address: http://{address}:8765\n"
    "Access token: {token}\n\n"
    "You can now close or restart Al-Baa and AI will keep running. "
    "Keep Ollama, Tailscale, and the computer powered on.":
        "خادم AI يعمل في الخلفية وسيبدأ تلقائيًا مع Windows.\n\n"
        "العنوان المحلي: http://{address}:8765\n"
        "رمز الوصول: {token}\n\n"
        "يمكنك الآن إغلاق أو إعادة تشغيل الباء وسيبقى AI يعمل. "
        "أبقِ Ollama وTailscale والكمبيوتر قيد التشغيل.",
    "The server started but didn't respond on port 8765.": "بدأ الخادم لكنه لم يستجب على المنفذ 8765.",
    "AI Network": "شبكة AI",
    "The background AI server was stopped and its auto-start was disabled.": "تم إيقاف خادم AI في الخلفية وتعطيل تشغيله التلقائي.",
    "AI Network Always On": "شبكة AI تعمل دائمًا",
    "The AI server is running in the background and will keep running when Al-Baa closes, starting automatically with Windows.":
        "خادم AI يعمل في الخلفية وسيبقى يعمل عند إغلاق الباء، وسيبدأ تلقائيًا مع Windows.",
    "AI Network Ready": "شبكة AI جاهزة",
    "Address: {address}\n\nKeep Al-Baa and Ollama running while using the mobile app.":
        "العنوان: {address}\n\nاترك الباء وOllama يعملان أثناء استخدام تطبيق الهاتف.",
    "The local AI server was stopped.": "تم إيقاف خادم الذكاء المحلي.",

    # -- AI providers --
    "Manage AI Providers...": "إدارة مزودي الذكاء الاصطناعي...",
    "Manage AI Providers": "إدارة مزودي الذكاء الاصطناعي",
    "Add, remove, and switch between AI providers": "أضف مزودي الذكاء الاصطناعي واحذفهم وبدّل بينهم",
    "Choose which configured AI provider to use": "اختر مزود الذكاء الاصطناعي الذي تريد استخدامه",
    "Choose a model for the active provider, or type its name": "اختر نموذجًا للمزود النشط أو اكتب اسمه",
    "AI Providers": "مزودو الذكاء الاصطناعي",
    "Add Provider": "إضافة مزود",
    "Edit Provider": "تعديل المزود",
    "Set as Default": "تعيين كافتراضي",
    "Remove": "حذف",
    "Remove Provider": "حذف المزود",
    'Remove "{name}"?': 'حذف "{name}"؟',
    "{entry} (default)": "{entry} (افتراضي)",
    "No AI provider is configured. Add one from the AI menu.":
        "لا يوجد مزود ذكاء اصطناعي مُعدّ. أضف واحدًا من قائمة AI.",
    "Could not get a response from {provider}. Make sure it's reachable and try again.":
        "تعذر الحصول على رد من {provider}. تأكد من إمكانية الوصول إليه وأعد المحاولة.",
    "Could not get a response from {provider}: {error}": "تعذر الحصول على رد من {provider}: {error}",
    "Label": "الاسم",
    "Type": "النوع",
    "Base URL": "عنوان الخادم (URL)",
    "API Key": "مفتاح API",
    "Default Model": "النموذج الافتراضي",
    "Test Connection": "اختبار الاتصال",
    "Testing…": "جارٍ الاختبار…",
    "Connection succeeded.": "نجح الاتصال.",
    "Connection failed: {error}": "فشل الاتصال: {error}",
    "Failed: {error}": "فشل: {error}",
    "Untitled Provider": "مزود بلا اسم",
    "OK": "موافق",

    # -- Android designer / export --
    "Could not read the app code.": "تعذر قراءة كود التطبيق.",
    "Could Not Open Designer": "تعذر فتح التصميم",
    "Fix the error first:\n\n{message}": "أصلح الخطأ أولاً:\n\n{message}",
    "Code": "الكود",
    "Designer": "تصميم",
    'This file isn\'t an Android app. Start with: تطبيق "App Name"':
        'هذا الملف ليس تطبيق Android. ابدأ بـ: تطبيق "اسم التطبيق"',
    "Choose an Android Project Folder": "اختر مجلد مشروع Android",
    "Replace Project Files": "استبدال ملفات المشروع",
    "main.py and buildozer.spec in the selected folder will be replaced. Continue?":
        "سيتم استبدال main.py و buildozer.spec في المجلد المحدد. هل تريد المتابعة؟",
    "Android project exported to:\n{directory}\n\nYou can push it to GitHub or build an APK via GitHub Actions.":
        "تم تصدير مشروع Android إلى:\n{directory}\n\nيمكنك رفعه إلى GitHub أو إنشاء APK عبر GitHub Actions.",
    "Not an App": "ليس تطبيقًا",
    "Open or create an Al-Baa app project first.": "افتح أو أنشئ مشروع تطبيق من الباء أولًا.",
    "Choose Where to Save the Windows App": "اختر مكان حفظ تطبيق Windows",
    "Export Failed": "تعذر التصدير",
    "Your app is ready to build.\nA real Windows app will now be built via GitHub.\n\nEXE save location: {directory}":
        "تم تجهيز تطبيقك للبناء.\nسيتم الآن إنشاء تطبيق Windows الحقيقي عبر GitHub.\n\nمكان حفظ EXE: {directory}",

    # -- GitHub flow --
    "GitHub operation in progress": "عملية GitHub جارية",
    "Installing GitHub": "تثبيت GitHub",
    "Signing In": "تسجيل الدخول",
    "Actions Permission": "صلاحية Actions",
    "Uploading Project": "رفع المشروع",
    "Building APK": "بناء APK",
    "Building EXE": "بناء EXE",
    "Preparing Windows Bundle": "تجهيز حزمة Windows",
    "Building iOS": "بناء iOS",
    "Preparing iOS App": "تجهيز تطبيق iOS",
    "  •  ~{min}–{max} min remaining": "  •  متبقي تقريبًا {min}–{max} د",
    " — usually takes 10–30 minutes": " — يستغرق عادةً 10–30 دقيقة",
    " — enter the code shown in the browser": " — أدخل الرمز الظاهر في المتصفح",
    "Cancel Operation": "إلغاء العملية",
    "Cancel the current GitHub operation?": "هل تريد إلغاء عملية GitHub الحالية؟",
    "Cancelling GitHub operation...": "جارٍ إلغاء عملية GitHub...",
    "A GitHub operation is already in progress.": "توجد عملية GitHub جارية بالفعل.",
    "Installing GitHub CLI via Winget...\n": "جارٍ تثبيت GitHub CLI عبر Winget...\n",
    "Installing GitHub CLI": "جارٍ تثبيت GitHub CLI",
    "GitHub is ready and signed in. You can push the app or build an APK.": "GitHub جاهز ومسجّل الدخول. يمكنك رفع التطبيق أو إنشاء APK.",
    "GitHub Ready": "GitHub جاهز",
    "Account connected, but workflow permission is required to build an APK.\n"
    "Enter the new code on GitHub to approve Actions permission.\n\n":
        "الحساب متصل، لكن صلاحية workflow مطلوبة لبناء APK.\n"
        "أدخل الرمز الجديد في GitHub للموافقة على صلاحية Actions.\n\n",
    "Adding GitHub Actions Permission": "إضافة صلاحية GitHub Actions",
    "GitHub will show a code and open your browser to sign in securely.\n"
    "Complete the sign-in in your browser and wait for the success message.\n\n":
        "سيعرض GitHub رمزًا ويفتح المتصفح لتسجيل الدخول بأمان.\n"
        "أكمل تسجيل الدخول في المتصفح وانتظر رسالة النجاح.\n\n",
    "Waiting to Sign In to GitHub": "في انتظار تسجيل الدخول إلى GitHub",
    "Could not start the GitHub tool.": "تعذر بدء أداة GitHub.",
    "Open or create an app before pushing to GitHub.": "افتح أو أنشئ تطبيقًا قبل الرفع إلى GitHub.",
    "Choose a Local Folder for the GitHub Project": "اختر مجلدًا محليًا لمشروع GitHub",
    "Could Not Prepare Project": "تعذر تجهيز المشروع",
    "Wait for the current GitHub operation to finish.": "انتظر حتى تنتهي عملية GitHub الحالية.",
    "GitHub Not Ready": "GitHub غير جاهز",
    "Click «Setup GitHub» and install the tool and sign in first.": "اضغط «إعداد GitHub» وثبّت الأداة وسجّل الدخول أولًا.",
    "GitHub Actions Permission Required": "صلاحية GitHub Actions مطلوبة",
    "Click «Setup GitHub» and approve workflow permission before pushing.": "اضغط «إعداد GitHub» ووافق على صلاحية workflow قبل الرفع.",
    "GitHub Repository Name": "اسم مستودع GitHub",
    "Enter the private repository name:": "اكتب اسم المستودع الخاص:",
    "Use only English letters, numbers, and . _ -": "استخدم حروفًا إنجليزية وأرقامًا و . _ - فقط.",
    "Preparing the Windows app for private cloud build...": "جارٍ تجهيز تطبيق Windows للبناء السحابي الخاص...",
    "Preparing the iOS app for a macOS build...": "جارٍ تجهيز تطبيق iOS للبناء على macOS...",
    "Pushing the app to GitHub...": "جارٍ رفع التطبيق إلى GitHub...",
    "Started building the APK on GitHub. The first build may take several minutes...":
        "بدأ إنشاء APK على GitHub. قد يستغرق البناء الأول عدة دقائق...",
    "Started building the Windows EXE and other platform bundles via GitHub...":
        "بدأ إنشاء Windows EXE وبقية حزم المنصات عبر GitHub...",
    "Started building the iOS Simulator app on GitHub macOS...": "بدأ إنشاء تطبيق iOS Simulator على GitHub macOS...",
    "GitHub operation cancelled.": "تم إلغاء عملية GitHub.",
    "Cancelled": "تم الإلغاء",
    "The GitHub operation was cancelled.": "تم إلغاء عملية GitHub.",
    "The GitHub operation failed with code {code}.": "فشلت عملية GitHub برمز {code}.",
    "Last details:\n{details}": "آخر التفاصيل:\n{details}",
    "GitHub Operation Failed": "فشلت عملية GitHub",
    "GitHub CLI installed. Complete sign-in now.": "تم تثبيت GitHub CLI. أكمل تسجيل الدخول الآن.",
    "Signed In": "تم تسجيل الدخول",
    "«Al-Baa» was successfully linked to your GitHub account.": "تم ربط «الباء» بحساب GitHub بنجاح.",
    "Permissions Complete": "اكتملت الصلاحيات",
    "GitHub Actions permission was added. You can now push the app and build an APK.":
        "تمت إضافة صلاحية GitHub Actions. يمكنك الآن رفع التطبيق وإنشاء APK.",
    "Pushed": "تم الرفع",
    "The app was successfully pushed to a private GitHub repository.": "تم رفع التطبيق إلى مستودع GitHub خاص بنجاح.",
    "APK built and downloaded successfully:\n{path}": "تم إنشاء وتنزيل APK بنجاح:\n{path}",
    "APK Built": "تم إنشاء APK",
    "APK Not Found": "لم يُعثر على APK",
    "GitHub succeeded but no APK file was found in the download folder.": "نجح GitHub لكن ملف APK غير موجود في مجلد التنزيل.",
    "Windows app built and downloaded successfully:\n{path}": "تم إنشاء وتنزيل تطبيق Windows بنجاح:\n{path}",
    "EXE Built": "تم إنشاء EXE",
    "EXE Not Found": "لم يُعثر على EXE",
    "The build finished, but no EXE or MSI was found inside the downloaded Windows bundle.":
        "انتهى البناء، لكن لم يُعثر على EXE أو MSI داخل ملف Windows الذي تم تنزيله.",
    "iOS Simulator app built and downloaded successfully:\n{path}\n\n"
    "This is the simulator build. Installing on an iPhone needs an Apple certificate and IPA signing.":
        "تم إنشاء وتنزيل تطبيق iOS Simulator بنجاح:\n{path}\n\n"
        "هذه النسخة للمحاكي. التثبيت على iPhone يحتاج شهادة Apple وتوقيع IPA.",
    "iOS Built": "تم إنشاء iOS",
    "iOS App Not Found": "لم يُعثر على تطبيق iOS",
    "The build finished, but no .app bundle was found inside the downloaded iOS bundle.":
        "انتهى البناء، لكن لم يُعثر على حزمة .app داخل ملف iOS الذي تم تنزيله.",
    "An APK build is already in progress. Wait for it to finish.": "يجري الآن إنشاء APK. انتظر حتى تنتهي العملية.",
    "APK tools aren't fully set up. First click: Install APK Tools.\n"
    "If you just installed WSL on Windows, restart the device and click Install again.":
        "أدوات APK غير مكتملة. اضغط أولًا على: تثبيت أدوات APK.\n"
        "إذا ثبّت Windows نظام WSL للتو، أعد تشغيل الجهاز ثم اضغط زر التثبيت مرة أخرى.",
    "APK Tools Not Ready": "أدوات APK غير جاهزة",
    "Can't build an APK right now.\n\n"
    "Click «Install APK Tools» and complete every step first. "
    "You may need to restart Windows.":
        "لا يمكن إنشاء APK الآن.\n\n"
        "اضغط «تثبيت أدوات APK» وأكمل جميع المراحل أولًا. "
        "قد تحتاج إلى إعادة تشغيل Windows.",
    "Starting Buildozer inside WSL2...\nWSL2, Buildozer, and the Android requirements must already be installed.\n\n":
        "بدء Buildozer داخل WSL2...\nيجب تثبيت WSL2 و Buildozer ومتطلبات Android مسبقاً.\n\n",
    "… Building APK": "… جارٍ إنشاء APK",
    "Building APK (local)": "جارٍ إنشاء APK",
    "APK tools are already being installed. Wait for it to finish.": "يجري الآن تثبيت أدوات APK. انتظر حتى تنتهي العملية.",
    "Checking WSL2 and Ubuntu...\n": "فحص WSL2 وUbuntu...\n",
    "… Checking": "… جارٍ الفحص",
    "Checking and installing APK tools": "جارٍ فحص وتثبيت أدوات APK",
    "The WSL2 and Ubuntu installation step finished.\n\n"
    "Restart Windows now, then open «Al-Baa» and click "
    "«Install APK Tools» again to finish Buildozer.":
        "انتهت مرحلة تثبيت WSL2 وUbuntu.\n\n"
        "أعد تشغيل Windows الآن، ثم افتح «الباء» واضغط "
        "«تثبيت أدوات APK» مرة أخرى لإكمال Buildozer.",
    "First Stage Complete": "انتهت المرحلة الأولى",
    "WSL2 installation failed with code {code}.\n\n"
    "If error 14098 appears (corrupt component store), «Al-Baa» "
    "can run the official Windows repair tools now. Start the repair?":
        "فشل تثبيت WSL2 برمز {code}.\n\n"
        "إذا ظهر الخطأ 14098 (مخزن المكونات تالف)، يستطيع «الباء» "
        "تشغيل أدوات إصلاح Windows الرسمية الآن. هل تريد بدء الإصلاح؟",
    "WSL2 Installation Failed": "فشل تثبيت WSL2",
    "Windows component repair finished. Restart the device, then click "
    "«Install APK Tools» again.":
        "انتهى إصلاح مكوّنات Windows. أعد تشغيل الجهاز، ثم اضغط "
        "«تثبيت أدوات APK» مرة أخرى.",
    "Windows Repair Complete": "اكتمل إصلاح Windows",
    "Windows repair didn't complete (code {code}). Check the result in the PowerShell window. "
    "You may need Windows Update or a Windows repair source matching your device's version.":
        "لم يكتمل إصلاح Windows (الرمز {code}). راجع النتيجة في نافذة PowerShell. "
        "قد تحتاج إلى Windows Update أو مصدر إصلاح Windows مطابق لإصدار جهازك.",
    "Could Not Repair Windows": "تعذر إصلاح Windows",
    "APK tools installed successfully. You can now click Build APK.": "اكتمل تثبيت أدوات APK بنجاح. يمكنك الآن الضغط على إنشاء APK.",
    "Installation Complete": "اكتمل التثبيت",
    "APK tools installation failed with code {code}. Check the output log.\n\n"
    "If Ubuntu is newly installed, open it once and finish its setup, then try again.":
        "فشل تثبيت أدوات APK برمز {code}. راجع سجل المخرجات.\n\n"
        "إذا كانت Ubuntu جديدة، افتحها مرة واحدة وأكمل إعدادها ثم حاول مجددًا.",
    "APK Tools Installation Failed": "فشل تثبيت أدوات APK",
    "… Installing WSL2": "… جارٍ تثبيت WSL2",
    "Windows will ask for administrator permission to install WSL2 and Ubuntu.\n"
    "Approve the prompt and wait until it finishes. Don't close «Al-Baa».\n\n":
        "سيطلب Windows صلاحية المسؤول لتثبيت WSL2 وUbuntu.\n"
        "وافق على النافذة وانتظر حتى تنتهي. لا تغلق «الباء».\n\n",
    "Starting to install Java, Buildozer, and Android requirements inside WSL2...\n"
    "This may take several minutes depending on your internet speed.\n\n":
        "بدء تثبيت Java وBuildozer ومتطلبات Android داخل WSL2...\n"
        "قد يستغرق ذلك عدة دقائق حسب سرعة الإنترنت.\n\n",
    "… Installing": "… جارٍ التثبيت",
    "… Repairing Windows": "… جارٍ إصلاح Windows",
    "Repairing Windows components": "جارٍ إصلاح مكوّنات Windows",
    "Starting to repair the Windows component store via DISM then SFC...\n"
    "This can take a long time. Don't close the PowerShell window.\n\n":
        "بدء إصلاح مخزن مكوّنات Windows عبر DISM ثم SFC...\n"
        "قد تستغرق العملية وقتًا طويلًا. لا تغلق نافذة PowerShell.\n\n",
    "↓ Install APK Tools": "↓ تثبيت أدوات APK",
    "Install the local Android APK build requirements": "تثبيت متطلبات إنشاء APK محليًا",
    "Export the Android project and build a debug APK": "تصدير مشروع Android وإنشاء ملف APK تجريبي",
    "Could not start WSL2/Buildozer. Make sure they're installed and on PATH inside WSL.":
        "تعذر بدء WSL2/Buildozer. تأكد من تثبيتهما وإضافتهما إلى PATH داخل WSL.",
    "Could Not Build APK": "تعذر إنشاء APK",
    "Could not run WSL2 or Buildozer. Click «Install APK Tools» and try again.":
        "تعذر تشغيل WSL2 أو Buildozer. اضغط «تثبيت أدوات APK» ثم حاول مجددًا.",
    "APK built successfully. You'll find it inside the project's bin folder.": "تم إنشاء APK بنجاح. ستجده داخل مجلد bin في المشروع.",
    "APK Built": "تم إنشاء APK",
    "APK build failed with exit code {code}. Check the Buildozer log in the output.":
        "فشل إنشاء APK برمز خروج {code}. راجع سجل Buildozer في المخرجات.",
    "APK Build Failed": "فشل إنشاء APK",

    # -- File ops / find / run --
    "Open File": "فتح ملف",
    "Al-Baa Files (*.apy);;Python (*.py);;All Files (*)": "ملفات الباء (*.apy);;Python (*.py);;All Files (*)",
    "Could not open the file:\n{error}": "تعذر فتح الملف:\n{error}",
    "Save File": "حفظ ملف",
    "Al-Baa Files (*.apy)": "ملفات الباء (*.apy)",
    "Saved": "تم الحفظ",
    "Could not save the file:\n{error}": "تعذر حفظ الملف:\n{error}",
    "Type a word to search": "اكتب كلمة للبحث",
    "No results": "لا توجد نتائج",
    "Found": "تم العثور",
    "Stop Preview": "إيقاف المعاينة",
    "App verified successfully. Use the File and Run menus to export or build an APK.":
        "تم التحقق من التطبيق بنجاح. استخدم قائمتي ملف وتشغيل للتصدير أو إنشاء APK.",
    "Ran successfully — no output.": "تم التنفيذ بنجاح — لا توجد مخرجات.",

    # -- Android Designer panel --
    "Al-Baa": "الباء",
    "Dark Social": "اجتماعي داكن",
    "Clean & Bright": "نظيف ومضيء",
    "Enter password": "أدخل كلمة المرور",
    "Strong password": "كلمة المرور قوية",
    "Use {min}+ characters with digits and symbols": "استخدم {min} خانات مع أرقام ورموز",
    "Elements": "العناصر",
    "+ Text": "+ نص",
    "+ Button": "+ زر",
    "+ Input Field": "+ حقل إدخال",
    "+ Video": "+ فيديو",
    "Video source": "مصدر الفيديو",
    "Properties": "الخصائص",
    "App Name": "اسم التطبيق",
    "Screen Background Color": "لون خلفية الشاشة",
    "App Templates": "قوالب التطبيق",
    "Element Name": "اسم العنصر",
    "Text": "النص",
    "Text Color": "لون النص",
    "Background Color": "لون الخلفية",
    "Reset to Default Colors": "إعادة الألوان الافتراضية",
    "Apply Changes": "تطبيق التغييرات",
    "Move Up": "تحريك لأعلى",
    "Move Down": "تحريك لأسفل",
    "Delete Element": "حذف العنصر",
    "Choose Screen Background Color": "اختر لون خلفية الشاشة",
    "Home": "الرئيسية",
    "Search": "البحث",
    "Alerts": "التنبيهات",
    "Messages": "الرسائل",
    "Invalid Text": "نص غير صالح",
    "Enter valid text for the bottom navigation button.": "اكتب نصًا صالحًا لزر الشريط السفلي.",
    "Invalid Name": "اسم غير صالح",
    "Use only letters, numbers, and underscores.": "استخدم حروفاً وأرقاماً وشرطة سفلية فقط.",
    "Duplicate Name": "اسم مكرر",
    "Another element already has this name.": "يوجد عنصر آخر بهذا الاسم.",
    "Double quotes aren't currently supported inside text.": "علامة الاقتباس المزدوجة غير مدعومة داخل النص حالياً.",
    "Choose Color": "اختر اللون",
    "Default": "افتراضي",
    "Text Color: {color}": "لون النص: {color}",
    "Background Color: {color}": "لون الخلفية: {color}",
    "Text Color: Auto": "لون النص: تلقائي",
    "Background Color: Auto": "لون الخلفية: تلقائي",
    "Page {name}": "صفحة {name}",
    "New Text": "نص جديد",
    "New Button": "زر جديد",
    "Type here": "اكتب هنا",
    "Screen Background Color: {color}": "لون خلفية الشاشة: {color}",

    # -- Language settings --
    "Settings": "الإعدادات",
    "Restart Required": "يتطلب إعادة التشغيل",
    "Al-Baa needs to restart to switch to {language}. Restart now?":
        "يحتاج الباء إلى إعادة التشغيل للتبديل إلى {language}. إعادة التشغيل الآن؟",
    "Run panel ready. Click ▶ Run to run the current program.": "لوحة التشغيل جاهزة. اضغط ▶ تشغيل لتشغيل البرنامج الحالي.",
    "Al-Baa\n\nAn Arabic programming language with an editor for writing and running programs.\nUse File > Open or the Open button to get started.":
        "الباء\n\nلغة برمجة عربية مع محرر لكتابة البرامج وتشغيلها.\nاستخدم ملف > فتح أو زر فتح لبدء العمل.",

    # -- Multi-language support (Flutter/Dart, first slice) --
    "New Flutter File": "ملف Flutter جديد",
    "main.dart": "main.dart",
    "New File (choose language)": "ملف جديد (اختر اللغة)",
    "NEW FILE — CHOOSE A LANGUAGE": "ملف جديد — اختر اللغة",
    "Al-Baa (.apy)": "الباء (.apy)",
    "Flutter (.dart)": "Flutter (.dart)",
    "The Arabic-keyword language this IDE is built for.": "لغة البرمجة بالكلمات المفتاحية العربية التي بُنيت لها هذه البيئة.",
    "Write and highlight Dart/Flutter code. Running and building are on the way.":
        "اكتب كود Dart/Flutter مع تلوين الصياغة. التشغيل والبناء قادمان قريباً.",
    "# Python preview isn't available for Flutter/Dart files.":
        "# معاينة Python غير متاحة لملفات Flutter/Dart.",
    "# No Python code has been generated yet.": "# لم يتم إنشاء كود Python بعد.",
    "\n# Error at line {line}, column {column}.": "\n# خطأ في السطر {line}، العمود {column}.",
    "# Fix or complete the Al-Baa code to generate Python.": "# أصلح أو أكمل كود الباء لإنشاء Python.",
    "Running Flutter/Dart files isn't supported yet -- it's on the way. "
    "For now, this tab is for writing and syntax-highlighting Dart code.":
        "تشغيل ملفات Flutter/Dart غير مدعوم بعد -- إنه قيد التطوير. "
        "حاليًا، هذه اللسان مخصص لكتابة كود Dart وتلوينه فقط.",
    "Al-Baa Files (*.apy);;Flutter Files (*.dart);;Python (*.py);;All Files (*)":
        "ملفات الباء (*.apy);;ملفات Flutter (*.dart);;Python (*.py);;All Files (*)",
    "Flutter Files (*.dart)": "ملفات Flutter (*.dart)",

    # -- Multi-language support (Python, first slice) --
    "New Python File": "ملف Python جديد",
    "main.py": "main.py",
    "Python (.py)": "Python (.py)",
    "Plain Python code, syntax-highlighted and runnable with ▶ Run.":
        "كود Python عادي، مع تلوين الصياغة وقابل للتشغيل بزر ▶ تشغيل.",
    "Python Files (*.py)": "ملفات Python (*.py)",
    "Running...": "قيد التشغيل...",
    "Finished (exit code {code}).": "انتهى (رمز الخروج {code}).",
    "Could not start Python.": "تعذر تشغيل Python.",
    "Wait for the current Python program to finish.": "انتظر حتى ينتهي برنامج Python الحالي.",
    "# This tab is already Python -- there's nothing to generate.\n# Click ▶ Run to run it.":
        "# هذا اللسان بلغة Python بالفعل -- لا يوجد ما يُنشأ.\n# اضغط ▶ تشغيل لتشغيله.",

    # -- Android Designer: AI chat widget --
    "+ AI Chat": "+ محادثة ذكاء",
    "Sample question": "سؤال تجريبي",
    "Sample AI answer": "رد تجريبي من الذكاء",
    "Type a message...": "اكتب رسالة...",
    "Thinking...": "يفكّر...",
    "Ask me anything -- I'm your local AI.": "اسألني أي شيء -- أنا الذكاء الاصطناعي المحلي الخاص بك.",
    "The model returned no answer.": "لم يُرجع النموذج إجابة.",
    "Model {model} isn't installed. Install it with: ollama pull {model}": (
        "النموذج {model} غير مثبت. ثبّته بالأمر: ollama pull {model}"
    ),
    "Couldn't run the local model: HTTP {code}": "تعذر تشغيل النموذج المحلي: HTTP {code}",
    "Couldn't connect to Ollama. Start Ollama and try again.": "تعذر الاتصال بـ Ollama. شغّل Ollama ثم حاول مجدداً.",
}
