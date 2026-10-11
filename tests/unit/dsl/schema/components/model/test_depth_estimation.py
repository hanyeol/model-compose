"""Unit tests for the depth-estimation component/action schemas."""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    DepthEstimationModelComponentConfig,
    HuggingfaceDepthEstimationModelComponentConfig,
    HuggingfaceDepthEstimationModelArchitecture,
    ModelProvider,
)
from mindor.dsl.schema.action import (
    DepthEstimationModelActionConfig,
    HuggingfaceDepthEstimationModelActionConfig,
)


COMPONENT_ADAPTER = TypeAdapter(DepthEstimationModelComponentConfig)
ACTION_ADAPTER = TypeAdapter(DepthEstimationModelActionConfig)


def _base(extra: dict | None = None) -> dict:
    raw = {
        "type": "model",
        "task": "depth-estimation",
        "driver": "huggingface",
        "model": "depth-anything/Depth-Anything-V2-Small-hf",
    }
    if extra:
        raw.update(extra)
    return raw


class TestComponentDiscriminator:
    def test_default_architecture_is_auto(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert isinstance(cfg, HuggingfaceDepthEstimationModelComponentConfig)
        assert cfg.architecture == HuggingfaceDepthEstimationModelArchitecture.AUTO

    def test_dpt_architecture_accepted(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"architecture": "dpt"}))
        assert cfg.architecture == HuggingfaceDepthEstimationModelArchitecture.DPT

    def test_depth_anything_architecture_accepted(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"architecture": "depth-anything"}))
        assert cfg.architecture == HuggingfaceDepthEstimationModelArchitecture.DEPTH_ANYTHING

    def test_unknown_architecture_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base({"architecture": "midas"}))


class TestModelInflation:
    def test_repo_id_becomes_huggingface_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert cfg.model.provider == ModelProvider.HUGGINGFACE
        assert cfg.model.repository == "depth-anything/Depth-Anything-V2-Small-hf"

    def test_local_path_becomes_local_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"model": "./weights/depth-anything"}))
        assert cfg.model.provider == ModelProvider.LOCAL
        assert cfg.model.path == "./weights/depth-anything"


class TestActionDefaults:
    def test_minimal_action_defaults(self):
        action = ACTION_ADAPTER.validate_python({"image": "in.png"})
        assert isinstance(action, HuggingfaceDepthEstimationModelActionConfig)
        assert action.image == "in.png"
        assert action.invert is False
        assert action.batch_size == 1
        assert action.params.input_size is None

    def test_invert_true_accepted(self):
        action = ACTION_ADAPTER.validate_python({"image": "in.png", "invert": True})
        assert action.invert is True

    def test_input_size_override_accepted(self):
        action = ACTION_ADAPTER.validate_python({
            "image": "in.png",
            "params": {"input_size": 518},
        })
        assert action.params.input_size == 518

    def test_image_accepts_list(self):
        action = ACTION_ADAPTER.validate_python({"image": ["a.png", "b.png"]})
        assert action.image == ["a.png", "b.png"]

    def test_variable_expressions_accepted(self):
        action = ACTION_ADAPTER.validate_python({
            "image": "${input.frames}",
            "invert": "${input.invert | false}",
            "batch_size": "${input.batch | 4}",
            "params": {"input_size": "${input.size | 518}"},
        })
        assert action.image == "${input.frames}"
        assert action.invert == "${input.invert | false}"
        assert action.batch_size == "${input.batch | 4}"
        assert action.params.input_size == "${input.size | 518}"
