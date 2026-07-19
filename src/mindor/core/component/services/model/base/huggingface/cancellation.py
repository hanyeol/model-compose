from typing import Optional, List
from mindor.core.foundation.cancellation import CancellationToken

def build_stopping_criteria(base: Optional[List], cancellation_token: Optional[CancellationToken]):
    from transformers import StoppingCriteria, StoppingCriteriaList

    criteria: List = list(base) if base else []

    if cancellation_token is not None:
        class CancellationTokenCriteria(StoppingCriteria):
            def __init__(self, token: CancellationToken):
                self._token = token

            def __call__(self, input_ids, scores, **kwargs) -> bool:
                return self._token.is_cancelled()

        criteria.append(CancellationTokenCriteria(cancellation_token))

    return StoppingCriteriaList(criteria) if criteria else None
