from __future__ import annotations

import math

from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize as l2_normalize

from app.pipeline.ranking import tokenize
from app.pipeline.types import ClusterSection, RankedArticle

# Minimum reduced dimensionality worth clustering on; below this SVD adds
# noise rather than signal, so very small corpora cluster on raw TF-IDF.
_MIN_SVD_COMPONENTS = 2
_MAX_SVD_COMPONENTS = 100

_STOPWORDS = {
    # minimal bilingual stopword list — good enough to keep cluster labels
    # from being dominated by function words, without a heavy NLP dependency
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
    "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по",
    "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из",
    "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или",
    "ни", "быть", "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "для",
    "этот", "эта", "это", "эти", "который", "которая", "которые", "их", "им",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "with", "as", "by", "at", "from", "that", "this",
    "it", "its", "has", "have", "had", "will", "can", "could", "new", "more",
}


def _default_label(terms: list[str]) -> str:
    cleaned = [t for t in terms if t.lower() not in _STOPWORDS]
    label = " / ".join(t.capitalize() for t in cleaned[:3])
    return label or "Общее"


def _embed(matrix) -> "object":
    """Reduces the sparse TF-IDF matrix to dense latent-semantic vectors via
    truncated SVD (classic LSA) and L2-normalizes them for cosine-like
    KMeans behavior. This is a fully local, no-download stand-in for a
    transformer embedding model: it still groups articles by co-occurring
    concepts rather than exact bag-of-words overlap, without fetching any
    model weights over the network."""

    n_components = min(_MAX_SVD_COMPONENTS, matrix.shape[1] - 1, matrix.shape[0] - 1)
    if n_components < _MIN_SVD_COMPONENTS:
        return matrix  # corpus too small for SVD to add signal; cluster on raw TF-IDF
    reduced = TruncatedSVD(n_components=n_components, random_state=42).fit_transform(matrix)
    return l2_normalize(reduced)


def cluster_articles(ranked: list[RankedArticle], min_clusters: int = 2, max_clusters: int = 6) -> list[ClusterSection]:
    """Groups already-ranked articles into topical sections using TF-IDF +
    LSA (SVD) embeddings + KMeans — a purely local, no-download alternative
    to a transformer embedding model — then labels each cluster from its
    top TF-IDF terms. Falls back to a single "Общее" section when there are
    too few articles to cluster meaningfully."""

    if len(ranked) < max(4, min_clusters * 2):
        return [ClusterSection(label="Общее", items=list(ranked))] if ranked else []

    texts = [f"{r.article.title} {r.article.text}" for r in ranked]
    vectorizer = TfidfVectorizer(
        tokenizer=tokenize,
        preprocessor=lambda x: x,
        token_pattern=None,
        stop_words=list(_STOPWORDS),
        max_features=3000,
    )
    matrix = vectorizer.fit_transform(texts)
    embeddings = _embed(matrix)

    n_clusters = max(min_clusters, min(max_clusters, round(math.sqrt(len(ranked) / 2))))
    n_clusters = min(n_clusters, len(ranked) - 1) if len(ranked) > 1 else 1
    n_clusters = max(n_clusters, 1)

    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(embeddings)

    feature_names = vectorizer.get_feature_names_out()
    buckets: dict[int, list[RankedArticle]] = {}
    for item, cluster_idx in zip(ranked, labels):
        buckets.setdefault(int(cluster_idx), []).append(item)

    sections: list[ClusterSection] = []
    for cluster_idx, items in buckets.items():
        member_rows = [i for i, lbl in enumerate(labels) if lbl == cluster_idx]
        centroid = matrix[member_rows].mean(axis=0)
        centroid_array = centroid.A1 if hasattr(centroid, "A1") else centroid
        top_indices = centroid_array.argsort()[::-1][:6]
        top_terms = [feature_names[i] for i in top_indices]
        sections.append(ClusterSection(label=_default_label(top_terms), items=items))

    sections.sort(key=lambda s: max((i.score for i in s.items), default=0.0), reverse=True)
    return sections
