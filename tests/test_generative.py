import pytest


@pytest.mark.ml
def test_local_lora_training_and_loading(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast
    from ml.generative.adapter import train_adapter, LocalDictionaryAdapter
    from ml.datasets.generation import generate
    from tests.test_datasets import entries

    vocabulary = {
        word: i
        for i, word in enumerate(
            [
                "[UNK]",
                "[PAD]",
                "[EOS]",
                "Define",
                "this",
                "dictionary",
                "word",
                "Give",
                "the",
                "for",
                "Answer",
                ":",
                "meaning",
            ]
            + [str(i) for i in range(10)]
            + [f"term{i}" for i in range(10)]
        )
    }
    raw = Tokenizer(WordLevel(vocabulary, unk_token="[UNK]"))
    raw.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=raw, unk_token="[UNK]", pad_token="[PAD]", eos_token="[EOS]"
    )
    base = tmp_path / "tiny-base"
    base.mkdir()
    tokenizer.save_pretrained(base)
    model = LlamaForCausalLM(
        LlamaConfig(
            vocab_size=len(vocabulary),
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=2,
            max_position_embeddings=128,
            bos_token_id=2,
            eos_token_id=2,
            pad_token_id=1,
        )
    )
    model.save_pretrained(base, safe_serialization=True)
    output = tmp_path / "output"
    output.mkdir()
    metrics = train_adapter(
        generate(entries(10)),
        base,
        output,
        {
            "epochs": 1,
            "batch_size": 4,
            "learning_rate": 0.001,
            "weight_decay": 0.01,
            "seed": 42,
            "max_length": 32,
            "lora_rank": 2,
            "patience": 1,
            "device": "cpu",
        },
        lambda *args: None,
    )
    assert metrics["experimental"]
    assert metrics["baseline"]["test_loss"] > 0 and metrics["fine_tuned"]["test_loss"] > 0
    loaded = LocalDictionaryAdapter.load(output)
    assert isinstance(loaded.generate("Define this dictionary word: term1", max_new_tokens=2), str)
