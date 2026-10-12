"""Unit tests for the image-edge-detection component/action schemas."""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    ImageEdgeDetectionModelComponentConfig,
    HedImageEdgeDetectionModelComponentConfig,
    PidinetImageEdgeDetectionModelComponentConfig,
    LineartImageEdgeDetectionModelComponentConfig,
    ImageEdgeDetectionModelFamily,
    ModelDriverType,
    ModelProvider,
)
from mindor.dsl.schema.action import (
    ImageEdgeDetectionModelActionConfig,
    HedImageEdgeDetectionModelActionConfig,
    PidinetImageEdgeDetectionModelActionConfig,
    LineartImageEdgeDetectionModelActionConfig,
)
from mindor.dsl.schema.action.impl.model.tasks.image_edge_detection.impl.custom.common import LineartVariant


COMPONENT_ADAPTER = TypeAdapter(ImageEdgeDetectionModelComponentConfig)


def _base(extra: dict | None = None) -> dict:
    raw = {
        "type": "model",
        "task": "image-edge-detection",
        "driver": "custom",
        "family": "hed",
        "model": "lllyasviel/Annotators",
    }
    if extra:
        raw.update(extra)
    return raw


class TestFamilyDiscriminator:
    def test_hed_family(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert isinstance(cfg, HedImageEdgeDetectionModelComponentConfig)
        assert cfg.family == ImageEdgeDetectionModelFamily.HED
        assert cfg.driver == ModelDriverType.CUSTOM

    def test_pidinet_family(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"family": "pidinet"}))
        assert isinstance(cfg, PidinetImageEdgeDetectionModelComponentConfig)
        assert cfg.family == ImageEdgeDetectionModelFamily.PIDINET

    def test_lineart_family_default_realistic(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"family": "lineart"}))
        assert isinstance(cfg, LineartImageEdgeDetectionModelComponentConfig)
        assert cfg.family == ImageEdgeDetectionModelFamily.LINEART
        assert cfg.variant == LineartVariant.REALISTIC

    def test_lineart_family_coarse_variant(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"family": "lineart", "variant": "coarse"}))
        assert cfg.variant == LineartVariant.COARSE

    def test_unknown_family_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base({"family": "canny"}))


class TestModelInflation:
    def test_repo_id_becomes_huggingface_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert cfg.model.provider == ModelProvider.HUGGINGFACE
        assert cfg.model.repository == "lllyasviel/Annotators"

    def test_filename_can_be_specified(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "model": {
                "provider": "huggingface",
                "repository": "lllyasviel/Annotators",
                "filename": "ControlNetHED.pth",
            },
        }))
        assert cfg.model.filename == "ControlNetHED.pth"


class TestActionDefaults:
    def test_hed_action_defaults(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "actions": [{"image": "${input.image}"}],
        }))
        action = cfg.actions[0]
        assert isinstance(action, HedImageEdgeDetectionModelActionConfig)
        assert action.invert is False
        assert action.batch_size == 1
        assert action.params.image_size == 512
        assert action.params.use_safe_mode is False

    def test_pidinet_action_defaults(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "family": "pidinet",
            "actions": [{"image": "${input.image}"}],
        }))
        action = cfg.actions[0]
        assert isinstance(action, PidinetImageEdgeDetectionModelActionConfig)
        assert action.params.image_size == 512
        assert action.params.use_safe_mode is False

    def test_lineart_action_has_no_safe_mode(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "family": "lineart",
            "actions": [{"image": "${input.image}", "params": {"image_size": 768}}],
        }))
        action = cfg.actions[0]
        assert isinstance(action, LineartImageEdgeDetectionModelActionConfig)
        assert action.params.image_size == 768
        assert not hasattr(action.params, "use_safe_mode")

    def test_variable_expressions_accepted(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "actions": [{
                "image": "${input.frames}",
                "invert": "${input.invert | false}",
                "batch_size": "${input.batch | 4}",
                "params": {
                    "image_size": "${input.size | 512}",
                    "use_safe_mode": "${input.safe | true}",
                },
            }],
        }))
        action = cfg.actions[0]
        assert action.image == "${input.frames}"
        assert action.invert == "${input.invert | false}"
        assert action.batch_size == "${input.batch | 4}"
        assert action.params.image_size == "${input.size | 512}"
        assert action.params.use_safe_mode == "${input.safe | true}"
