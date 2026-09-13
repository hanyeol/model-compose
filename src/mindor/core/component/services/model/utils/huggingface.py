import json
import os

def is_checkpoint_prequantized(path: str) -> bool:
    # transformers/diffusers write a `quantization_config` block into
    # `config.json` when a checkpoint is saved pre-quantized (bnb, gptq,
    # awq, etc.); `from_pretrained` reads it back to pick the right loader.

    config_path = os.path.join(path, "config.json")

    if not os.path.isfile(config_path):
        return False

    with open(config_path) as f:
        config = json.load(f)

    return "quantization_config" in config
