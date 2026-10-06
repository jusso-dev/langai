"""Safe JSON classifier artifacts; no untrusted pickle/joblib deserialization."""

import json
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, log_loss


def evaluate(y, scores):
    prediction = scores >= 0.5
    return {
        "accuracy": float(accuracy_score(y, prediction)),
        "macro_f1": float(f1_score(y, prediction, average="macro")),
        "roc_auc": float(roc_auc_score(y, scores)),
        "log_loss": float(log_loss(y, np.c_[1 - scores, scores], labels=[0, 1])),
        "sample_count": len(y),
    }


def train(dataset, emit):
    splits = {
        s: [r for r in dataset["views"]["language_identification"] if r["split"] == s]
        for s in ["train", "validation", "test"]
    }
    for split, rows in splits.items():
        if {r["label"] for r in rows} != {0, 1}:
            raise ValueError(f"{split} requires both dictionary words and approved external negatives")
    vectorizer = TfidfVectorizer(
        analyzer="char", ngram_range=(1, 5), lowercase=False, min_df=1, max_features=50000
    )
    x = vectorizer.fit_transform([r["text"] for r in splits["train"]])
    y = [r["label"] for r in splits["train"]]
    xv = vectorizer.transform([r["text"] for r in splits["validation"]])
    yv = [r["label"] for r in splits["validation"]]
    xt = vectorizer.transform([r["text"] for r in splits["test"]])
    yt = [r["label"] for r in splits["test"]]
    metrics, models = {}, {}
    for name, estimator in [
        ("logistic_regression", LogisticRegression(max_iter=2000, random_state=42, class_weight="balanced")),
        ("linear_svm", LinearSVC(random_state=42, class_weight="balanced")),
    ]:
        estimator.fit(x, y)
        # Calibration fitted ONLY on validation, test is never used for model selection/calibration.
        calibrator = LogisticRegression(random_state=42).fit(
            estimator.decision_function(xv).reshape(-1, 1), yv
        )
        scores = calibrator.predict_proba(estimator.decision_function(xt).reshape(-1, 1))[:, 1]
        metrics[name] = evaluate(yt, scores)
        models[name] = {
            "coef": estimator.coef_[0].tolist(),
            "intercept": float(estimator.intercept_[0]),
            "calibration_coef": float(calibrator.coef_[0, 0]),
            "calibration_intercept": float(calibrator.intercept_[0]),
        }
        emit(f"{name} baseline evaluated", metrics[name])
    # Fixed default, deliberately not selected using test results.
    model = NgramClassifier(
        {
            "vocabulary": {k: int(v) for k, v in vectorizer.vocabulary_.items()},
            "idf": vectorizer.idf_.tolist(),
            "models": models,
            "selected": "logistic_regression",
        }
    )
    return model, {
        "baselines": metrics,
        "selected": "logistic_regression",
        "calibration": "validation-only sigmoid",
        "caution": "Confidence is relative to configured negatives, not proof of language membership.",
    }


class NgramClassifier:
    def __init__(self, artifact):
        self.artifact = artifact
        self.vectorizer = TfidfVectorizer(
            analyzer="char", ngram_range=(1, 5), lowercase=False, vocabulary=artifact["vocabulary"]
        )
        self.vectorizer.idf_ = np.array(artifact["idf"])

    def predict(self, texts):
        x = self.vectorizer.transform(texts)
        model = self.artifact["models"][self.artifact["selected"]]
        decision = np.asarray(x @ np.array(model["coef"])) + model["intercept"]
        logits = decision * model["calibration_coef"] + model["calibration_intercept"]
        probability = 1 / (1 + np.exp(-np.clip(logits, -50, 50)))
        return [
            {
                "positive_probability": float(p),
                "confidence": float(max(p, 1 - p)),
                "is_language": bool(p >= 0.5),
            }
            for p in probability
        ]

    def save(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "classifier.json").write_text(json.dumps(self.artifact))

    @classmethod
    def load(cls, path):
        return cls(json.loads((Path(path) / "classifier.json").read_text()))
