"""Unit tests for the PESTO music-pitch-estimation component/action schemas.

The component discriminates on ``backend`` (``torch`` / ``onnx``) with runtime
cross-field validators that enforce the valid combinations:

- ``backend: onnx`` requires ``streaming`` + ``sample_rate``.
- ``streaming`` requires ``sample_rate`` and is mutually exclusive with ``step_size``.
- ``providers`` is onnx-only.

Offline ``torch`` runs fill in ``step_size: 10.0`` by default.
"""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    MusicPitchEstimationModelComponentConfig,
    PestoMusicPitchEstimationModelComponentConfig,
    PestoBackend,
    ModelProvider,
)
from mindor.dsl.schema.action import (
    MusicPitchEstimationModelActionConfig,
    PestoMusicPitchEstimationModelActionConfig,
    PitchUnit,
)


COMPONENT_ADAPTER = TypeAdapter(MusicPitchEstimationModelComponentConfig)
ACTION_ADAPTER = TypeAdapter(MusicPitchEstimationModelActionConfig)


def _base(extra: dict | None = None) -> dict:
    raw = {
        "type": "model",
        "task": "music-pitch-estimation",
        "driver": "custom",
        "family": "pesto",
        "model": "mir-1k_g7",
    }
    if extra:
        raw.update(extra)
    return raw


class TestBackendDiscriminator:
    def test_default_backend_is_torch(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert isinstance(cfg, PestoMusicPitchEstimationModelComponentConfig)
        assert cfg.backend == PestoBackend.TORCH

    def test_explicit_onnx_backend(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "backend": "onnx",
            "model": "./weights/mir-1k_g7.onnx",
            "sample_rate": 44100,
            "streaming": {"chunk_size": 1024},
        }))
        assert cfg.backend == PestoBackend.ONNX

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_base({"backend": "tensorrt"}))


class TestModelInflation:
    def test_bundled_name_becomes_named_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"model": "mir-1k_g7"}))
        assert cfg.model.provider == ModelProvider.NAMED
        assert cfg.model.name == "mir-1k_g7"

    def test_local_ckpt_path_becomes_local_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({"model": "./weights/custom.ckpt"}))
        assert cfg.model.provider == ModelProvider.LOCAL
        assert cfg.model.path == "./weights/custom.ckpt"

    def test_local_onnx_path_becomes_local_provider(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "backend": "onnx",
            "model": "./weights/mir-1k_g7_44100_1024.onnx",
            "sample_rate": 44100,
            "streaming": {"chunk_size": 1024},
        }))
        assert cfg.model.provider == ModelProvider.LOCAL
        assert cfg.model.path.endswith(".onnx")


class TestOfflineDefaults:
    def test_offline_torch_fills_default_step_size(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base())
        assert cfg.step_size == 10.0
        assert cfg.streaming is None

    def test_streaming_leaves_step_size_unset(self):
        cfg = COMPONENT_ADAPTER.validate_python(_base({
            "sample_rate": 48000,
            "streaming": {"chunk_size": 240},
        }))
        assert cfg.step_size is None


class TestBackendRequirements:
    def test_onnx_without_streaming_rejected(self):
        with pytest.raises(ValidationError, match="requires 'streaming'"):
            COMPONENT_ADAPTER.validate_python(_base({
                "backend": "onnx",
                "model": "./weights/m.onnx",
                "sample_rate": 44100,
            }))

    def test_onnx_without_sample_rate_rejected(self):
        with pytest.raises(ValidationError, match="requires 'sample_rate'"):
            COMPONENT_ADAPTER.validate_python(_base({
                "backend": "onnx",
                "model": "./weights/m.onnx",
                "streaming": {"chunk_size": 1024},
            }))

    def test_onnx_with_step_size_rejected(self):
        with pytest.raises(ValidationError, match="torch-only"):
            COMPONENT_ADAPTER.validate_python(_base({
                "backend": "onnx",
                "model": "./weights/m.onnx",
                "sample_rate": 44100,
                "step_size": 5.0,
                "streaming": {"chunk_size": 1024},
            }))

    def test_streaming_without_sample_rate_rejected(self):
        with pytest.raises(ValidationError, match="'streaming' requires 'sample_rate'"):
            COMPONENT_ADAPTER.validate_python(_base({
                "streaming": {"chunk_size": 240},
            }))

    def test_streaming_and_step_size_mutually_exclusive(self):
        with pytest.raises(ValidationError, match="mutually exclusive"):
            COMPONENT_ADAPTER.validate_python(_base({
                "sample_rate": 48000,
                "step_size": 5.0,
                "streaming": {"chunk_size": 240},
            }))

    def test_providers_rejected_on_torch_backend(self):
        with pytest.raises(ValidationError, match="only applies when backend=onnx"):
            COMPONENT_ADAPTER.validate_python(_base({
                "providers": ["CPUExecutionProvider"],
            }))


class TestActionDefaults:
    def test_streaming_defaults_to_false(self):
        action = ACTION_ADAPTER.validate_python({"audio": "in.wav"})
        assert isinstance(action, PestoMusicPitchEstimationModelActionConfig)
        assert action.streaming is False
        assert action.params.reduction == "alwa"
        assert action.params.pitch_unit == PitchUnit.HZ
        assert action.params.num_chunks == 1
        assert action.return_activations is False

    def test_streaming_true_accepted(self):
        action = ACTION_ADAPTER.validate_python({"audio": "in.wav", "streaming": True})
        assert action.streaming is True

    def test_pitch_unit_semitone_accepted(self):
        action = ACTION_ADAPTER.validate_python({
            "audio": "in.wav",
            "params": {"pitch_unit": "semitone"},
        })
        assert action.params.pitch_unit == PitchUnit.SEMITONE

    def test_unknown_pitch_unit_rejected(self):
        with pytest.raises(ValidationError):
            ACTION_ADAPTER.validate_python({
                "audio": "in.wav",
                "params": {"pitch_unit": "cents"},
            })

    def test_unknown_reduction_rejected(self):
        with pytest.raises(ValidationError):
            ACTION_ADAPTER.validate_python({
                "audio": "in.wav",
                "params": {"reduction": "medianized"},
            })
