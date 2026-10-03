from scripts.evaluate import precision_recall_at_k


def test_perfect_ranking_gives_full_precision_and_recall():
    ranked = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    precision, recall = precision_recall_at_k(ranked, relevant, k=3)
    assert precision == 1.0
    assert recall == 1.0


def test_partial_hits_computed_correctly():
    ranked = ["a", "x", "b", "y", "z"]
    relevant = {"a", "b", "c"}
    precision, recall = precision_recall_at_k(ranked, relevant, k=5)
    assert precision == 2 / 5
    assert recall == 2 / 3


def test_k_larger_than_ranked_list_is_safe():
    ranked = ["a"]
    relevant = {"a", "b"}
    precision, recall = precision_recall_at_k(ranked, relevant, k=10)
    assert precision == 1.0
    assert recall == 0.5


def test_no_relevant_items_gives_zero_recall_without_division_error():
    precision, recall = precision_recall_at_k(["a", "b"], set(), k=5)
    assert recall == 0.0


def test_empty_ranked_list_gives_zero_precision_without_division_error():
    precision, recall = precision_recall_at_k([], {"a"}, k=5)
    assert precision == 0.0
