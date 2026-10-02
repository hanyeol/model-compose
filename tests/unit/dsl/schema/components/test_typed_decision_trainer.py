"""Unit tests for the ``typed-decision`` model-trainer schema tree.

Checks that:
  * every family (`clef`, `laya`, `nimble`, `kev`) resolves through the task +
    driver discriminator pair,
  * each family-specific config carries the fields the driver reads at runtime
    (`choice_loss_weight` on Clef, `freeze_encoder` on Laya, `base_model` on
    Nimble, pointer-head knobs on Kev),
  * the shared ``quantization requires lora`` guard still fires through the
    typed-decision subtree,
  * action-side column defaults (`state`, `schema`, `answers`) are preserved
    and the ``schema`` alias collision with ``BaseModel.schema`` has no effect
    on the trainer config.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.dsl.schema.component import ModelTrainerComponentConfig


_TRAINER_ADAPTER = TypeAdapter(ModelTrainerComponentConfig)


def _base(driver: str, **overrides) -> dict:
    return {
        "id": "trainer",
        "type": "model-trainer",
        "task": "typed-decision",
        "driver": driver,
        "model": "placeholder",
        **overrides,
    }


class TestDriverDiscriminator:
    def test_clef_parses(self):
        cfg = _TRAINER_ADAPTER.validate_python(_base("clef", model="Cloudflare/clef"))
        assert cfg.driver.value == "clef"
        assert cfg.choice_loss_weight == 1.0
        assert cfg.noul_loss_weight == 1.0
        assert cfg.score_loss_weight == 1.0

    def test_laya_parses_with_preset_and_freeze_encoder(self):
        cfg = _TRAINER_ADAPTER.validate_python(_base(
            "laya",
            model="convaiinnovations/laya",
            preset="typed-decisions",
            freeze_encoder=True,
        ))
        assert cfg.driver.value == "laya"
        assert cfg.preset.value == "typed-decisions"
        assert cfg.freeze_encoder is True

    def test_kev_parses_with_pointer_head_knobs(self):
        cfg = _TRAINER_ADAPTER.validate_python(_base(
            "kev",
            model="jaredpalmer/kev-4b",
            lora={"rank": 8},
            max_state_length=4096,
            max_branch_length=4096,
            train_pointer_head=True,
        ))
        assert cfg.driver.value == "kev"
        assert cfg.max_state_length == 4096
        assert cfg.max_branch_length == 4096
        assert cfg.train_pointer_head is True

    def test_nimble_requires_base_model(self):
        cfg = _TRAINER_ADAPTER.validate_python(_base(
            "nimble",
            model="user/nimble-adapter",
            base_model="Qwen/Qwen3.5-9B",
            lora={"rank": 8},
        ))
        assert cfg.driver.value == "nimble"
        # base_model is lifted into a ModelConfig the same way `model` is.
        assert cfg.base_model.repository == "Qwen/Qwen3.5-9B"

    def test_unknown_driver_rejected(self):
        with pytest.raises(ValidationError):
            _TRAINER_ADAPTER.validate_python(_base("unsloth", model="x"))


class TestSharedGuards:
    def test_quantization_without_lora_rejected(self):
        with pytest.raises(ValidationError, match="quantization requires 'lora'"):
            _TRAINER_ADAPTER.validate_python(_base(
                "clef", model="Cloudflare/clef", quantization="int8",
            ))

    def test_quantization_with_lora_accepted(self):
        cfg = _TRAINER_ADAPTER.validate_python(_base(
            "nimble",
            model="user/nimble-adapter",
            base_model="Qwen/Qwen3.5-9B",
            lora={"rank": 8},
            quantization="int4",
        ))
        assert cfg.quantization.type.value == "int4"


class TestActionConfig:
    def test_defaults_match_native_columns(self):
        action = TypedDecisionModelTrainerActionConfig.model_validate({"dataset": "./train.jsonl"})
        assert action.state_column == "state"
        assert action.schema_column == "schema"
        assert action.answers_column == "answers"

    def test_dataset_required(self):
        with pytest.raises(ValidationError):
            TypedDecisionModelTrainerActionConfig.model_validate({})

    def test_evaluation_dataset_optional(self):
        action = TypedDecisionModelTrainerActionConfig.model_validate({
            "dataset": "./train.jsonl",
            "evaluation_dataset": "./eval.jsonl",
        })
        assert action.evaluation_dataset == "./eval.jsonl"
