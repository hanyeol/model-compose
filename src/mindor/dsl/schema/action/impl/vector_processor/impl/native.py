from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonVectorProcessorActionConfig, VectorProcessorActionMethod, VectorSimilarityMetric

# Vector values are passed through variable references in most cases.
# Accept `str` (interpolation) or any nested list/scalar shape.
VectorInput = Union[str, float, int, List[Any]]

class VectorProcessorCosineSimilarityActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.COSINE_SIMILARITY]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")

class VectorProcessorDotProductActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DOT_PRODUCT]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")

class VectorProcessorEuclideanDistanceActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.EUCLIDEAN_DISTANCE]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")

class VectorProcessorNormalizeActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.NORMALIZE]
    vector: VectorInput = Field(..., description="Vector or batch of vectors to L2-normalize.")

class VectorProcessorMeanActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.MEAN]
    vectors: VectorInput = Field(..., description="Vectors to average (list of vectors).")
    axis: Union[int, str] = Field(default=0, description="Axis along which to take the mean.")

class VectorProcessorSumActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SUM]
    vectors: VectorInput = Field(..., description="Vectors to sum (list of vectors).")
    axis: Union[int, str] = Field(default=0, description="Axis along which to sum.")

class VectorProcessorTopKActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.TOP_K]
    query: VectorInput = Field(..., description="Query vector.")
    candidates: VectorInput = Field(..., description="Candidate vectors, or a nested list of vectors (auto-flattened).")
    k: Union[int, str] = Field(default=1, description="Number of top matches to return.")
    metric: Union[VectorSimilarityMetric, str] = Field(default=VectorSimilarityMetric.COSINE, description="Similarity metric.")
    flatten: Union[bool, str] = Field(default=True, description="If true, flatten one nesting level of `candidates` before scoring. Original nested indices are preserved in the output.")

class VectorProcessorThresholdFilterActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.THRESHOLD_FILTER]
    query: VectorInput = Field(..., description="Query vector.")
    candidates: VectorInput = Field(..., description="Candidate vectors, or a nested list of vectors (auto-flattened).")
    threshold: Union[float, str] = Field(..., description="Score threshold. Semantics depend on metric: for cosine/dot, keep score >= threshold; for euclidean, keep distance <= threshold.")
    metric: Union[VectorSimilarityMetric, str] = Field(default=VectorSimilarityMetric.COSINE, description="Similarity metric.")
    flatten: Union[bool, str] = Field(default=True, description="If true, flatten one nesting level of `candidates` before scoring.")

NativeVectorProcessorActionConfig = Annotated[
    Union[
        VectorProcessorCosineSimilarityActionConfig,
        VectorProcessorDotProductActionConfig,
        VectorProcessorEuclideanDistanceActionConfig,
        VectorProcessorNormalizeActionConfig,
        VectorProcessorMeanActionConfig,
        VectorProcessorSumActionConfig,
        VectorProcessorTopKActionConfig,
        VectorProcessorThresholdFilterActionConfig,
    ],
    Field(discriminator="method")
]
