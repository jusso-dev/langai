import copy
import random
import numpy as np
import torch
from ml.evaluation.retrieval import retrieval


def fit(encoder, dataset, config, emit):
    from datasets import Dataset as HFDataset

    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    # HF datasets contains only frozen, provenance-bearing training samples.
    train = HFDataset.from_list([s for s in dataset["views"]["semantic"] if s["split"] == "train"])
    validation = [s for s in dataset["views"]["semantic"] if s["split"] == "validation"]
    if not len(train) or not any(s["label"] == 0 for s in train):
        raise ValueError("Contrastive training requires at least two unrelated training concepts")
    validation_ids = {k for k, v in dataset["manifest"]["entry_splits"].items() if v == "validation"}
    optimizer = torch.optim.AdamW(
        encoder.model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    best, best_state, stale, history = -1.0, None, 0, []

    def loss_for(batch):
        a = encoder.differentiable([s["anchor"] for s in batch])
        b = encoder.differentiable([s["text"] for s in batch])
        y = torch.tensor([s["label"] for s in batch], device=a.device)
        cosine = (a * b).sum(-1)
        return (y * (1 - cosine).pow(2) + (1 - y) * torch.relu(cosine - config["margin"]).pow(2)).mean()

    for epoch in range(config["epochs"]):
        encoder.model.train()
        order = list(range(len(train)))
        random.Random(seed + epoch).shuffle(order)
        total, count = 0.0, 0
        for start in range(0, len(order), config["batch_size"]):
            batch = [train[i] for i in order[start : start + config["batch_size"]]]
            optimizer.zero_grad()
            loss = loss_for(batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(encoder.model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.detach()) * len(batch)
            count += len(batch)
            emit(
                "Training batch",
                {
                    "epoch": epoch + 1,
                    "epochs": config["epochs"],
                    "progress": (epoch + count / len(train)) / config["epochs"],
                    "train_loss": total / count,
                },
            )
        should_eval = (epoch + 1) % config["evaluation_frequency"] == 0 or epoch == config["epochs"] - 1
        if not should_eval:
            continue
        encoder.model.eval()
        with torch.no_grad():
            val_loss = sum(
                float(loss_for(validation[i : i + config["batch_size"]]))
                * len(validation[i : i + config["batch_size"]])
                for i in range(0, len(validation), config["batch_size"])
            ) / len(validation)
        metrics = retrieval(encoder, dataset["entries"], validation_ids)
        row = {
            "epoch": epoch + 1,
            "epochs": config["epochs"],
            "train_loss": total / count,
            "validation_loss": val_loss,
            "validation_mrr": metrics["mrr"],
            "validation_recall_at_1": metrics["recall_at_1"],
            "validation_recall_at_5": metrics["recall_at_5"],
        }
        history.append(row)
        emit("Validation complete", row)
        if metrics["mrr"] > best:
            best, best_state, stale = (
                metrics["mrr"],
                copy.deepcopy({k: v.cpu() for k, v in encoder.model.state_dict().items()}),
                0,
            )
        else:
            stale += 1
            if stale >= config["patience"]:
                emit("Early stopping: validation MRR did not improve", {"epoch": epoch + 1})
                break
    encoder.model.load_state_dict(best_state)
    return {
        "history": history,
        "best_validation_mrr": best,
        "loss": "labelled cosine contrastive; within-split negatives",
    }
