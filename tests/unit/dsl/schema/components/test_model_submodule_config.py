"""Unit tests for ``ModelSubmoduleConfig`` schema validation.

Covers the three accepted input forms (bare string, flat shorthand, nested),
the shared ``inflate_model`` validator that promotes model keys and infers
providers, and the inherited behavior of subclasses (``DiffusionIpAdapterConfig``,
``PeftAdapterConfig``).
"""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.component import (
    DiffusionIpAdapterConfig,
    HuggingfaceModelConfig,
    LocalModelConfig,
    ModelPrecision,
    ModelProvider,
    ModelSubmoduleConfig,
    NamedModelConfig,
    PeftAdapterConfig,
    PeftAdapterType,
)


class TestStringShorthand:
    """A bare string value desugars into ``{model: {provider, repository|path}}``."""

    def test_hub_repo_string_infers_huggingface_provider(self):
        cfg = ModelSubmoduleConfig.model_validate("stabilityai/stable-diffusion-xl-base-1.0")
        assert isinstance(cfg.model, HuggingfaceModelConfig)
        assert cfg.model.repository == "stabilityai/stable-diffusion-xl-base-1.0"

    def test_absolute_posix_path_infers_local_provider(self):
        cfg = ModelSubmoduleConfig.model_validate("/weights/sdxl-vae")
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.path == "/weights/sdxl-vae"

    def test_tilde_user_path_infers_local_provider_and_expands(self):
        cfg = ModelSubmoduleConfig.model_validate("~/weights/vae")
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.path.endswith("/weights/vae")
        assert not cfg.model.path.startswith("~")

    def test_relative_dot_path_infers_local_provider(self):
        cfg = ModelSubmoduleConfig.model_validate("./weights/vae")
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.path == "./weights/vae"

    def test_string_shorthand_leaves_siblings_at_defaults(self):
        cfg = ModelSubmoduleConfig.model_validate("org/repo")
        assert cfg.checkpoint is None
        assert cfg.precision is None
        assert cfg.low_cpu_mem_usage is False


class TestFlatShorthand:
    """Flat form (``provider`` / ``repository`` at the top level alongside
    submodule-level fields) desugars by moving the model keys into a nested
    ``model`` dict."""

    def test_flat_provider_plus_repository_promoted_to_model(self):
        cfg = ModelSubmoduleConfig.model_validate({"provider": "huggingface", "repository": "h94/IP-Adapter"})
        assert isinstance(cfg.model, HuggingfaceModelConfig)
        assert cfg.model.repository == "h94/IP-Adapter"

    def test_flat_repository_only_infers_huggingface_provider(self):
        cfg = ModelSubmoduleConfig.model_validate({"repository": "h94/IP-Adapter"})
        assert isinstance(cfg.model, HuggingfaceModelConfig)
        assert cfg.model.repository == "h94/IP-Adapter"

    def test_flat_path_only_infers_local_provider(self):
        cfg = ModelSubmoduleConfig.model_validate({"path": "/weights/vae"})
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.path == "/weights/vae"

    def test_flat_name_only_infers_named_provider(self):
        cfg = ModelSubmoduleConfig.model_validate({"name": "sdxl-base"})
        assert isinstance(cfg.model, NamedModelConfig)
        assert cfg.model.name == "sdxl-base"

    def test_flat_with_revision_promotes_only_model_keys(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "repository": "org/repo",
            "revision": "v1.2.3",
        })
        assert cfg.model.repository == "org/repo"
        assert cfg.model.revision == "v1.2.3"

    def test_flat_with_sibling_checkpoint_separates_into_model_and_submodule(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "repository": "h94/IP-Adapter",
            "checkpoint": "models/ip-adapter_sd15.bin",
        })
        assert cfg.model.repository == "h94/IP-Adapter"
        assert cfg.checkpoint == "models/ip-adapter_sd15.bin"

    def test_flat_with_sibling_precision_separates_into_model_and_submodule(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "repository": "org/repo",
            "precision": "bfloat16",
        })
        assert cfg.model.repository == "org/repo"
        assert cfg.precision == ModelPrecision.BFLOAT16

    def test_flat_with_all_submodule_siblings(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "repository": "org/repo",
            "checkpoint": "w.safetensors",
            "precision": "float16",
            "low_cpu_mem_usage": True,
        })
        assert cfg.model.repository == "org/repo"
        assert cfg.checkpoint == "w.safetensors"
        assert cfg.precision == ModelPrecision.FLOAT16
        assert cfg.low_cpu_mem_usage is True


class TestNestedForm:
    """Nested form passes ``model`` through directly; sibling fields stay at
    the submodule level."""

    def test_nested_dict_pass_through(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "model": {"provider": "huggingface", "repository": "org/repo"},
            "checkpoint": "w.bin",
        })
        assert cfg.model.repository == "org/repo"
        assert cfg.checkpoint == "w.bin"

    def test_nested_model_as_string_desugars_to_hub_repo(self):
        cfg = ModelSubmoduleConfig.model_validate({"model": "org/repo"})
        assert isinstance(cfg.model, HuggingfaceModelConfig)
        assert cfg.model.repository == "org/repo"

    def test_nested_model_as_absolute_path_desugars_to_local(self):
        cfg = ModelSubmoduleConfig.model_validate({"model": "/weights/x"})
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.path == "/weights/x"

    def test_nested_model_without_provider_but_with_repository(self):
        cfg = ModelSubmoduleConfig.model_validate({"model": {"repository": "org/repo"}})
        assert isinstance(cfg.model, HuggingfaceModelConfig)

    def test_nested_model_without_provider_but_with_path(self):
        cfg = ModelSubmoduleConfig.model_validate({"model": {"path": "/weights/x"}})
        assert isinstance(cfg.model, LocalModelConfig)

    def test_nested_model_without_provider_but_with_name(self):
        cfg = ModelSubmoduleConfig.model_validate({"model": {"name": "preset-a"}})
        assert isinstance(cfg.model, NamedModelConfig)


class TestInvalidInputs:
    """Inputs the schema must reject."""

    def test_empty_dict_rejected(self):
        with pytest.raises(ValidationError):
            ModelSubmoduleConfig.model_validate({})

    def test_only_sibling_without_model_rejected(self):
        # `checkpoint` alone has no model to attach to.
        with pytest.raises(ValidationError):
            ModelSubmoduleConfig.model_validate({"checkpoint": "w.bin"})

    def test_unknown_top_level_key_is_silently_dropped(self):
        # Pydantic's default `extra="ignore"` applies — unknown keys travel
        # along with the model-key promotion and are dropped by both the
        # submodule config and the inner `HuggingfaceModelConfig`.
        cfg = ModelSubmoduleConfig.model_validate({"repository": "org/repo", "unknown_key": "x"})
        assert cfg.model.repository == "org/repo"

    def test_bad_precision_value_rejected(self):
        with pytest.raises(ValidationError):
            ModelSubmoduleConfig.model_validate({
                "repository": "org/repo",
                "precision": "quadruple-float",
            })


class TestInheritance:
    """Subclasses inherit ``inflate_model`` and all submodule-level fields."""

    def test_diffusion_ip_adapter_accepts_string_shorthand(self):
        cfg = DiffusionIpAdapterConfig.model_validate("h94/IP-Adapter")
        assert cfg.model.repository == "h94/IP-Adapter"
        assert cfg.image_encoder is None

    def test_diffusion_ip_adapter_flat_with_checkpoint(self):
        cfg = DiffusionIpAdapterConfig.model_validate({
            "repository": "h94/IP-Adapter",
            "checkpoint": "models/ip-adapter_sd15.bin",
        })
        assert cfg.model.repository == "h94/IP-Adapter"
        assert cfg.checkpoint == "models/ip-adapter_sd15.bin"

    def test_diffusion_ip_adapter_flat_with_image_encoder_string(self):
        cfg = DiffusionIpAdapterConfig.model_validate({
            "repository": "h94/IP-Adapter",
            "checkpoint": "models/ip-adapter_sd15.bin",
            "image_encoder": "laion/CLIP-ViT-H-14",
        })
        assert cfg.image_encoder.model.repository == "laion/CLIP-ViT-H-14"

    def test_diffusion_ip_adapter_nested_image_encoder_dict(self):
        cfg = DiffusionIpAdapterConfig.model_validate({
            "model": "h94/IP-Adapter",
            "image_encoder": {"repository": "laion/CLIP-ViT-H-14", "precision": "float16"},
        })
        assert cfg.image_encoder.model.repository == "laion/CLIP-ViT-H-14"
        assert cfg.image_encoder.precision == ModelPrecision.FLOAT16

    def test_peft_adapter_flat_shorthand_with_type_and_weight(self):
        cfg = PeftAdapterConfig.model_validate({
            "type": "lora",
            "repository": "org/my-lora",
            "weight": 0.8,
            "checkpoint": "adapter.safetensors",
        })
        assert cfg.type == PeftAdapterType.LORA
        assert cfg.model.repository == "org/my-lora"
        assert cfg.weight == 0.8
        assert cfg.checkpoint == "adapter.safetensors"

    def test_peft_adapter_requires_type(self):
        with pytest.raises(ValidationError):
            PeftAdapterConfig.model_validate({"repository": "org/my-lora"})

    def test_peft_adapter_inherits_precision_and_low_cpu_mem_usage(self):
        cfg = PeftAdapterConfig.model_validate({
            "type": "lora",
            "repository": "org/lora",
            "precision": "float16",
            "low_cpu_mem_usage": True,
        })
        assert cfg.precision == ModelPrecision.FLOAT16
        assert cfg.low_cpu_mem_usage is True

    def test_peft_adapter_name_sibling_promoted_in_flat_form(self):
        cfg = PeftAdapterConfig.model_validate({
            "type": "lora",
            "repository": "org/lora",
            "name": "style_1",
            "weight": 0.5,
        })
        # NOTE: `name` collides with NamedModelConfig's `name`. The flat
        # shorthand treats it as a submodule-level sibling (PeftAdapter.name)
        # because the dict also carries `repository` which triggers the
        # HuggingFace provider path.
        assert cfg.model.repository == "org/lora"
        assert cfg.name == "style_1"

    def test_subclass_identity_preserved(self):
        peft = PeftAdapterConfig.model_validate({"type": "lora", "repository": "org/lora"})
        assert isinstance(peft, PeftAdapterConfig)
        assert isinstance(peft, ModelSubmoduleConfig)

        ip = DiffusionIpAdapterConfig.model_validate("h94/IP-Adapter")
        assert isinstance(ip, DiffusionIpAdapterConfig)
        assert isinstance(ip, ModelSubmoduleConfig)


class TestProviderInference:
    """``inflate_model`` picks the provider when it is omitted; the
    HuggingFace side also accepts an explicit provider kwarg."""

    def test_explicit_provider_wins_over_inference(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "model": {"provider": "huggingface", "repository": "org/repo"},
        })
        assert cfg.model.provider == ModelProvider.HUGGINGFACE

    def test_explicit_local_provider_requires_path_or_url(self):
        with pytest.raises(ValidationError):
            ModelSubmoduleConfig.model_validate({"model": {"provider": "local"}})

    def test_local_provider_accepts_url_without_path(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "model": {"provider": "local", "url": "https://example.com/weights.bin"},
        })
        assert isinstance(cfg.model, LocalModelConfig)
        assert cfg.model.url.endpoint == "https://example.com/weights.bin"


class TestFlatShorthandIsolation:
    """The flat shorthand only triggers when none of the model keys are
    already nested under ``model`` — nested form must not get re-promoted."""

    def test_nested_model_with_flat_siblings_does_not_re_promote(self):
        cfg = ModelSubmoduleConfig.model_validate({
            "model": {"provider": "huggingface", "repository": "org/repo"},
            "checkpoint": "w.bin",
            "precision": "float16",
        })
        assert cfg.model.repository == "org/repo"
        assert cfg.checkpoint == "w.bin"
        assert cfg.precision == ModelPrecision.FLOAT16

    def test_dict_without_any_model_key_falls_through_to_default_validation(self):
        # No model-ish key means flat-shorthand doesn't engage; missing
        # `model` is then a plain required-field validation error.
        with pytest.raises(ValidationError) as exc_info:
            ModelSubmoduleConfig.model_validate({"precision": "float16"})
        # Confirm it fails because `model` is missing, not because of a
        # malformed inflate call.
        assert any(err["loc"] == ("model",) for err in exc_info.value.errors())
