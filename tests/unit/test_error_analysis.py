from visolexnorm.evaluation.errors import analyze_rows, categorize


def test_category_precedence() -> None:
    assert categorize("ko", "không", "không") == "correct"
    assert categorize("hello", "hello", "xin chào") == "over-normalization"
    assert categorize("ko", "không", "ko") == "missed"
    assert categorize("mng", "mọi người", "abc") == "one-to-many"
    assert categorize("không biết", "kbt", "abc") == "many-to-one"
    assert categorize("ko", "không", "khum", weak_label_noise=True) == "suspected-weak-label-noise"
    assert categorize("ko", "không", "khum") == "wrong"


def test_analysis_keeps_test_order_and_compares_models() -> None:
    base = {"id": "test-1", "input_text": "ko", "target_text": "không"}
    a, b = {**base, "prediction_text": "không"}, {**base, "prediction_text": "ko"}
    result = analyze_rows([a], [b], set())
    assert result[0]["id"] == "test-1"
    assert result[0]["model_a_category"] == "correct"
    assert result[0]["better_model"] == "model_a"


def test_audit_selection_is_deterministic_in_input_id_order() -> None:
    rows_a = []
    rows_b = []
    for identifier in ("test-2", "test-1"):
        base = {"id": identifier, "input_text": "ko", "target_text": "không"}
        rows_a.append({**base, "prediction_text": "ko"})
        rows_b.append({**base, "prediction_text": "không"})
    records = analyze_rows(rows_a, rows_b, set())
    audit = [record for record in records if record["model_a_category"] != "correct"][:1]
    assert audit[0]["id"] == "test-2"