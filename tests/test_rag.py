from arabicpy.rag import _ocr_result_text, context_for, import_document, retrieve


def test_retrieves_function_knowledge_for_arabic_question():
    results = retrieve("كيف اكتب دالة ترجع ناتج جمع رقمين؟", limit=2)
    assert results
    assert results[0].title == "الدوال"
    assert "ارجع" in results[0].text


def test_retrieves_list_indexing_example():
    context = context_for("كيف اطبع اول عنصر من قائمة باستخدام الفهرس؟")
    assert "ارقام[0]" in context


def test_unknown_question_warns_against_invention():
    context = context_for("كوانتم مجهول تماما xyzzy")
    assert "لا تخترع" in context


def test_retrieval_is_shared_and_bounded():
    assert len(retrieve("اطبع شرط دالة قائمة حلقة", limit=2)) == 2


def test_imported_text_document_becomes_searchable(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setattr("arabicpy.rag.documents_directory", lambda: library)
    library.mkdir()
    source = tmp_path / "guide.md"
    source.write_text("ميزة السلحفاة ترسم دائرة تعليمية خاصة", encoding="utf-8")
    imported = import_document(source)
    assert imported.parent == library
    assert "السلحفاة" in context_for("كيف استخدم السلحفاة؟")


def test_rejects_unsupported_or_large_document(tmp_path):
    source = tmp_path / "danger.exe"
    source.write_bytes(b"not a document")
    try:
        import_document(source)
    except ValueError as error:
        assert "غير مدعوم" in str(error)
    else:
        raise AssertionError("unsupported document was accepted")


def test_extracts_text_from_modern_ocr_result_shape():
    class Result:
        json = {"res": {"rec_texts": ["مرحبا", "من مستند مصور"]}}

    assert _ocr_result_text([Result()]) == "مرحبا\nمن مستند مصور"
