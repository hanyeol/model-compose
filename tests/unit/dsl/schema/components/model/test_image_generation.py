"""Unit tests for the architecture-injection validator on Huggingface image
generation components.

The component config has an ``architecture`` discriminator (``sdxl``, ``flux``,
``hunyuan-image``); each of its actions also has the same field. The
``inject_architecture_into_actions`` validator auto-injects the component's
architecture into actions that omit it, so users don't have to repeat it on
every action.
"""

from pydantic import TypeAdapter

from mindor.dsl.schema.component.impl.model.impl.image_generation.impl.huggingface import (
    SdxlHuggingfaceImageGenerationModelComponentConfig,
    FluxHuggingfaceImageGenerationModelComponentConfig,
)


class TestInjectArchitectureIntoActions:
    def test_actions_without_architecture_get_injected(self):
        cfg = SdxlHuggingfaceImageGenerationModelComponentConfig.model_validate({
            "type": "model",
            "task": "image-generation",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "driver": "huggingface",
            "architecture": "sdxl",
            "actions": [{"text": "a cat"}, {"text": "a dog"}],
        })
        assert len(cfg.actions) == 2
        assert all(action.architecture.value == "sdxl" for action in cfg.actions)

    def test_explicit_action_architecture_preserved(self):
        # When the action already declares architecture (matching the component's),
        # the validator should leave it untouched.
        cfg = SdxlHuggingfaceImageGenerationModelComponentConfig.model_validate({
            "type": "model",
            "task": "image-generation",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "driver": "huggingface",
            "architecture": "sdxl",
            "actions": [{"text": "a cat", "architecture": "sdxl"}],
        })
        assert cfg.actions[0].architecture.value == "sdxl"

    def test_flux_architecture_injected(self):
        cfg = FluxHuggingfaceImageGenerationModelComponentConfig.model_validate({
            "type": "model",
            "task": "image-generation",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "driver": "huggingface",
            "architecture": "flux",
            "actions": [{"text": "a fox"}],
        })
        assert cfg.actions[0].architecture.value == "flux"

    def test_empty_actions_no_injection(self):
        cfg = SdxlHuggingfaceImageGenerationModelComponentConfig.model_validate({
            "type": "model",
            "task": "image-generation",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "driver": "huggingface",
            "architecture": "sdxl",
            "actions": [],
        })
        assert cfg.actions == []
