from typing import Union, Annotated
from pydantic import Field
from .common import (
    VectorProcessorSimilarityActionConfig,
    VectorProcessorDistanceActionConfig,
    VectorProcessorDotProductActionConfig,
    VectorProcessorNormalizeActionConfig,
    VectorProcessorMeanActionConfig,
    VectorProcessorSumActionConfig,
    VectorProcessorTopKActionConfig,
    VectorProcessorThresholdFilterActionConfig,
)

NativeVectorProcessorActionConfig = Annotated[
    Union[
        VectorProcessorSimilarityActionConfig,
        VectorProcessorDistanceActionConfig,
        VectorProcessorDotProductActionConfig,
        VectorProcessorNormalizeActionConfig,
        VectorProcessorMeanActionConfig,
        VectorProcessorSumActionConfig,
        VectorProcessorTopKActionConfig,
        VectorProcessorThresholdFilterActionConfig,
    ],
    Field(discriminator="method")
]
