"""Opt-in dictionary recall experiment. This does not teach conversational competence."""

import math
from pathlib import Path
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainerCallback,
    TrainingArguments,
    default_data_collator,
)
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model


def train_adapter(snapshot, base_path, output, config, emit):
    tokenizer = AutoTokenizer.from_pretrained(str(base_path), local_files_only=True, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(base_path),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=torch.float32,
    )
    max_length = config["max_length"]

    def tokenize(row):
        prompt = tokenizer(row["prompt"], add_special_tokens=False)["input_ids"]
        answer = tokenizer(row["response"] + tokenizer.eos_token, add_special_tokens=False)["input_ids"]
        # Reserve room for the response; never train on padding or the instruction prefix.
        prompt = prompt[: max_length // 2]
        ids = (prompt + answer)[:max_length]
        labels = ([-100] * len(prompt) + answer)[:max_length]
        mask = [1] * len(ids)
        padding = max_length - len(ids)
        return {
            "input_ids": ids + [tokenizer.pad_token_id] * padding,
            "attention_mask": mask + [0] * padding,
            "labels": labels + [-100] * padding,
        }

    splits = {
        s: Dataset.from_list([tokenize(r) for r in snapshot["views"]["instructions"] if r["split"] == s])
        for s in ["train", "validation", "test"]
    }

    class Logs(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            emit(
                "Experimental adapter training",
                {
                    **(logs or {}),
                    "epoch": state.epoch,
                    "progress": state.global_step / max(1, state.max_steps),
                },
            )

    args = TrainingArguments(
        output_dir=str(Path(output) / "checkpoints"),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        learning_rate=config["learning_rate"],
        weight_decay=config["weight_decay"],
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        use_cpu=config["device"] == "cpu",
        report_to=[],
        logging_steps=1,
        seed=config["seed"],
        data_seed=config["seed"],
        dataloader_num_workers=0,
        disable_tqdm=True,
    )
    baseline_trainer = Trainer(
        model=model, args=args, eval_dataset=splits["validation"], data_collator=default_data_collator
    )
    baseline = baseline_trainer.evaluate(splits["test"])
    del baseline_trainer
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=config["lora_rank"],
            lora_alpha=2 * config["lora_rank"],
            lora_dropout=0.05,
            target_modules="all-linear",
        ),
    )
    from transformers import EarlyStoppingCallback

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=splits["train"],
        eval_dataset=splits["validation"],
        data_collator=default_data_collator,
        callbacks=[Logs(), EarlyStoppingCallback(early_stopping_patience=config["patience"])],
    )
    trainer.train()
    trained = trainer.evaluate(splits["test"])
    path = Path(output) / "adapter"
    model.save_pretrained(path, safe_serialization=True)
    tokenizer.save_pretrained(path)
    # Self-contained local base, so deployments never fetch data or models on inference.
    import shutil

    shutil.copytree(base_path, Path(output) / "base", dirs_exist_ok=True, symlinks=False)
    return {
        "experimental": True,
        "baseline": {
            "test_loss": baseline["eval_loss"],
            "perplexity": math.exp(min(50, baseline["eval_loss"])),
        },
        "fine_tuned": {
            "test_loss": trained["eval_loss"],
            "perplexity": math.exp(min(50, trained["eval_loss"])),
        },
        "warning": "Dictionary recall only. No claims of grammar, translation or fluency.",
    }


class LocalDictionaryAdapter:
    """Local research interface, deliberately separate from semantic inference endpoints."""

    def __init__(self, path):
        from peft import PeftModel

        self.path = Path(path)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.path / "adapter", local_files_only=True, trust_remote_code=False
        )
        base = AutoModelForCausalLM.from_pretrained(
            self.path / "base", local_files_only=True, trust_remote_code=False, use_safetensors=True
        )
        self.model = PeftModel.from_pretrained(base, self.path / "adapter", local_files_only=True)
        self.model.eval()

    def generate(self, prompt, max_new_tokens=128):
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=256, return_token_type_ids=False
        )
        with torch.no_grad():
            tokens = self.model.generate(
                **inputs,
                max_new_tokens=min(max_new_tokens, 256),
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        return self.tokenizer.decode(tokens[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True)

    def save(self, path):
        import shutil

        shutil.copytree(self.path, path, dirs_exist_ok=True, symlinks=False)

    @classmethod
    def load(cls, path):
        return cls(path)
