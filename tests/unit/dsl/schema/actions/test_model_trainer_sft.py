"""Unit tests for ``SftModelTrainerActionConfig.validate_data_columns``."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.action.impl.model_trainer.tasks.sft import SftModelTrainerActionConfig


class TestValidateDataColumns:
    def test_text_column_only_ok(self):
        cfg = SftModelTrainerActionConfig(dataset="d", text_column="text")
        assert cfg.text_column == "text"

    def test_prompt_and_response_columns_ok(self):
        cfg = SftModelTrainerActionConfig(
            dataset="d", prompt_column="prompt", response_column="response"
        )
        assert cfg.prompt_column == "prompt"
        assert cfg.response_column == "response"

    def test_no_columns_rejected(self):
        with pytest.raises(ValidationError, match="'text_column' or both 'prompt_column' and 'response_column'"):
            SftModelTrainerActionConfig(dataset="d")

    def test_prompt_only_rejected(self):
        with pytest.raises(ValidationError, match="'text_column' or both 'prompt_column' and 'response_column'"):
            SftModelTrainerActionConfig(dataset="d", prompt_column="p")

    def test_response_only_rejected(self):
        with pytest.raises(ValidationError, match="'text_column' or both 'prompt_column' and 'response_column'"):
            SftModelTrainerActionConfig(dataset="d", response_column="r")

    def test_all_columns_ok(self):
        cfg = SftModelTrainerActionConfig(
            dataset="d", text_column="t", prompt_column="p", response_column="r", system_column="s"
        )
        assert cfg.system_column == "s"
