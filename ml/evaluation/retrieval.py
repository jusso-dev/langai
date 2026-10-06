import numpy as np
from ml.datasets.generation import identity


def summarize(values):
    a = np.asarray(values, dtype=float)
    return {
        "count": len(a),
        "mean": float(a.mean()) if len(a) else None,
        "std": float(a.std()) if len(a) else None,
        "p05": float(np.quantile(a, 0.05)) if len(a) else None,
        "p50": float(np.quantile(a, 0.5)) if len(a) else None,
        "p95": float(np.quantile(a, 0.95)) if len(a) else None,
    }


def retrieval(encoder, entries, query_ids):
    # Candidate pool is the entire frozen dictionary, not only the tiny held-out subset.
    candidates = [(e["id"], d) for e in entries for d in e["definitions"]]
    queries = [e for e in entries if e["id"] in query_ids]
    if not queries or not candidates:
        raise ValueError("Evaluation requires held-out queries and dictionary candidates")
    candidate_embeddings = encoder.encode([d for _, d in candidates])
    query_embeddings = encoder.encode([e["normalized_headword"] for e in queries])
    ranks, positives, negatives = [], [], []
    for q, vector in zip(queries, query_embeddings):
        scores = candidate_embeddings @ vector
        correct = {identity(d) for d in q["definitions"]}
        relevant = np.array([identity(d) in correct for _, d in candidates])
        order = np.argsort(-scores, kind="stable")
        ranks.append(next(i + 1 for i, index in enumerate(order) if relevant[index]))
        positives.extend(scores[relevant].tolist())
        negatives.extend(scores[~relevant][:100].tolist())
    return {
        **{f"recall_at_{k}": float(np.mean(np.asarray(ranks) <= k)) for k in [1, 5, 10]},
        "mrr": float(np.mean(1 / np.asarray(ranks))),
        "query_count": len(queries),
        "candidate_count": len(candidates),
        "cosine_similarity": {"positive": summarize(positives), "negative": summarize(negatives)},
        "protocol": "held-out headword retrieval against all dictionary definitions; all exact meaning matches relevant",
    }
