"""Regression tests for ``HuggingfaceTextEmbeddingTaskAction._resolve_text_features``.

transformers 5.x changed CLIP/SigLIP/X-CLIP's ``get_text_features`` to return a
``BaseModelOutputWithPooling`` instead of a bare tensor. Older versions returned
a tensor directly. The resolver must handle both so that CLIPScore-style
pipelines don't blow up when a fresh venv pulls transformers>=5.0.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from mindor.core.component.services.model.tasks.text_embedding.huggingface import (
    HuggingfaceTextEmbeddingTaskAction,
)


def _make_action() -> HuggingfaceTextEmbeddingTaskAction:
    return HuggingfaceTextEmbeddingTaskAction.__new__(HuggingfaceTextEmbeddingTaskAction)


class TestResolveTextFeatures:
    def test_bare_tensor_passthrough(self):
        action = _make_action()
        tensor = torch.tensor([[1.0, 2.0, 3.0]])

        result = action._resolve_text_features(tensor, attention_mask=None, pooling="mean")

        assert result is tensor

    def test_pooler_output_returned(self):
        action = _make_action()
        pooled = torch.tensor([[0.5, 0.5]])
        output = SimpleNamespace(pooler_output=pooled, last_hidden_state=None)

        result = action._resolve_text_features(output, attention_mask=None, pooling="mean")

        assert torch.equal(result, pooled)

    def test_last_hidden_state_fallback_mean_pooled(self):
        action = _make_action()
        hidden = torch.tensor([[[1.0, 2.0], [3.0, 4.0]]])
        output = SimpleNamespace(pooler_output=None, last_hidden_state=hidden)

        result = action._resolve_text_features(output, attention_mask=None, pooling="mean")

        assert torch.equal(result, torch.tensor([[2.0, 3.0]]))

    def test_last_hidden_state_fallback_respects_attention_mask(self):
        action = _make_action()
        hidden = torch.tensor([[[1.0, 1.0], [9.0, 9.0]]])
        mask = torch.tensor([[1, 0]])
        output = SimpleNamespace(pooler_output=None, last_hidden_state=hidden)

        result = action._resolve_text_features(output, attention_mask=mask, pooling="mean")

        assert torch.equal(result, torch.tensor([[1.0, 1.0]]))

    def test_unknown_shape_raises(self):
        action = _make_action()
        output = SimpleNamespace(pooler_output=None, last_hidden_state=None)

        with pytest.raises(ValueError, match="Cannot extract text features"):
            action._resolve_text_features(output, attention_mask=None, pooling="mean")
