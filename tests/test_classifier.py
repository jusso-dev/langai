from ml.classifiers.ngram import NgramClassifier, train
from ml.datasets.generation import generate
from tests.test_datasets import entries


def test_classifier_baselines_and_json_roundtrip(tmp_path):
    data = generate(
        entries(),
        negatives={
            "id": "n",
            "texts": [f"different-{i}" for i in range(40)],
            "governance": {"training_allowed": True},
        },
    )
    model, metrics = train(data, lambda *args: None)
    assert set(metrics["baselines"]) == {"linear_svm", "logistic_regression"}
    model.save(tmp_path)
    result = NgramClassifier.load(tmp_path).predict(["term10", "different-2"])
    expected = model.predict(["term10", "different-2"])
    assert result == expected
    assert all(0 <= r["confidence"] <= 1 for r in result)
