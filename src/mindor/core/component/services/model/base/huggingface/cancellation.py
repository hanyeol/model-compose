from __future__ import annotations
from typing import TYPE_CHECKING
from mindor.core.foundation.cancellation import CancellationToken

if TYPE_CHECKING:
    from transformers import StoppingCriteria

def create_cancellation_criteria(cancellation_token: CancellationToken) -> "StoppingCriteria":
    from transformers import StoppingCriteria

    class CancellationCriteria(StoppingCriteria):
        def __init__(self, token: CancellationToken):
            super().__init__()

            self._token = token

        def __call__(self, input_ids, scores, **kwargs) -> bool:
            return self._token.is_cancelled()

    return CancellationCriteria(cancellation_token)
