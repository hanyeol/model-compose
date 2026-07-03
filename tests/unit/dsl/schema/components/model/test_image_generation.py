"""Unit tests for the Huggingface image-generation component/action schemas.

The component discriminates on ``architecture`` (``sdxl`` / ``flux`` /
``hunyuan-image``); each variant carries a driver-specific action config with
its own per-architecture default parameters. The action config itself has no
``architecture`` field — the discriminator lives entirely on the component.
"""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    ImageGenerationModelComponentConfig,
    SdxlHuggingfaceImageGenerationModelComponentConfig,
    FluxHuggingfaceImageGenerationModelComponentConfig,
    HunyuanImageHuggingfaceImageGenerationModelComponentConfig,
)
from mindor.dsl.schema.action import (
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
    HuggingfaceImageGenerationModelArchitecture,
)


COMPONENT_ADAPTER = TypeAdapter(ImageGenerationModelComponentConfig)


def _base(architecture: str, extra: dict | None = None) -> dict:
    raw = {
        "type": "model",
        "task": "image-generation",
        "driver": "huggingface",
        "architecture": architecture,
        "model": "stabilityai/stable-diffusion-xl-base-1.0",
    }
    if extra:
        raw.update(extra)
    return raw


class TestArchitectureDiscriminator:
    def test_sdxl_component_resolves_to_sdxl_action(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": "a cat"}],
        }))
        assert isinstance(cfg, SdxlHuggingfaceImageGenerationModelComponentConfig)
        assert len(cfg.actions) == 1
        assert isinstance(cfg.actions[0], SdxlHuggingfaceImageGenerationModelActionConfig)

    def test_flux_component_resolves_to_flux_action(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("flux", {
            "model": "black-forest-labs/FLUX.1-dev",
            "actions": [{"prompt": "a cat"}],
        }))
        assert isinstance(cfg, FluxHuggingfaceImageGenerationModelComponentConfig)
        assert isinstance(cfg.actions[0], FluxHuggingfaceImageGenerationModelActionConfig)

    def test_hunyuan_image_component_resolves_to_hunyuan_action(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("hunyuan-image", {
            "model": "tencent/HunyuanImage",
            "actions": [{"prompt": "a cat"}],
        }))
        assert isinstance(cfg, HunyuanImageHuggingfaceImageGenerationModelComponentConfig)
        assert isinstance(cfg.actions[0], HunyuanImageHuggingfaceImageGenerationModelActionConfig)

    def test_unknown_architecture_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base("stable-diffusion-15", {
                "actions": [{"prompt": "a cat"}],
            }))


class TestArchitectureDefaults:
    """Per-architecture params classes should carry their own defaults."""

    def test_sdxl_defaults(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": "a cat"}],
        }))
        p = cfg.actions[0].params
        assert p.num_inference_steps == 30
        assert p.guidance_scale == 7.5
        assert p.width == 1024
        assert p.height == 1024
        assert p.negative_prompt is None

    def test_flux_defaults(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("flux", {
            "model": "black-forest-labs/FLUX.1-dev",
            "actions": [{"prompt": "a cat"}],
        }))
        p = cfg.actions[0].params
        assert p.num_inference_steps == 28
        assert p.guidance_scale == 3.5
        assert p.max_sequence_length == 512

    def test_hunyuan_image_defaults(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("hunyuan-image", {
            "model": "tencent/HunyuanImage",
            "actions": [{"prompt": "a cat"}],
        }))
        p = cfg.actions[0].params
        assert p.num_inference_steps == 50
        assert p.distilled_guidance_scale == 3.25

    def test_user_override_wins_over_default(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{
                "prompt": "a cat",
                "params": {"num_inference_steps": 40, "guidance_scale": 9.0},
            }],
        }))
        p = cfg.actions[0].params
        assert p.num_inference_steps == 40
        assert p.guidance_scale == 9.0


class TestActionSchema:
    def test_action_has_no_architecture_field(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": "a cat"}],
        }))
        action = cfg.actions[0]
        assert not hasattr(action, "architecture")

    def test_prompt_required(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base("sdxl", {
                "actions": [{}],
            }))

    def test_prompt_accepts_string(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": "a lone lantern"}],
        }))
        assert cfg.actions[0].prompt == "a lone lantern"

    def test_prompt_accepts_list(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": ["a cat", "a dog"]}],
        }))
        assert cfg.actions[0].prompt == ["a cat", "a dog"]

    def test_prompt_accepts_variable_expression(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base("sdxl", {
            "actions": [{"prompt": "${input.prompt}"}],
        }))
        assert cfg.actions[0].prompt == "${input.prompt}"

    def test_legacy_text_field_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base("sdxl", {
                "actions": [{"text": "a cat"}],
            }))


class TestTaskDiscriminator:
    def test_legacy_task_text_to_image_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base("sdxl", {
                "task": "text-to-image",
                "actions": [{"prompt": "a cat"}],
            }))


class TestArchitectureEnum:
    def test_enum_values(self):
        assert HuggingfaceImageGenerationModelArchitecture.SDXL == "sdxl"
        assert HuggingfaceImageGenerationModelArchitecture.FLUX == "flux"
        assert HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE == "hunyuan-image"
