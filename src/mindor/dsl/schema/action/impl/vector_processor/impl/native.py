from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonVectorProcessorActionConfig, VectorProcessorActionMethod, SimilarityMetric, DistanceMetric

# Vector values are passed through variable references in most cases.
# Accept `str` (interpolation) or any nested list/scalar shape.
VectorInput = Union[str, float, int, List[Any]]

# For ranking (top-k / threshold-filter) the metric may be either a similarity
# or a distance measure; sign convention (higher-is-better vs lower-is-better)
# is decided by which enum the value belongs to.
RankingMetric = Union[SimilarityMetric, DistanceMetric, str]

class VectorProcessorSimilarityActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SIMILARITY]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[SimilarityMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity metric.")

class VectorProcessorDistanceActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DISTANCE]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[DistanceMetric, str] = Field(default=DistanceMetric.EUCLIDEAN, description="Distance metric.")

class VectorProcessorDotProductActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DOT_PRODUCT]
    vector: VectorInput = Field(..., description="Vector or batch of vectors.")
    other: VectorInput = Field(..., description="Vector or batch of vectors. Broadcasts against `vector`.")

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
    candidates: VectorInput = Field(..., description="Flat list of candidate vectors.")
    k: Union[int, str] = Field(default=1, description="Number of top matches to return.")
    metric: RankingMetric = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric.")

class VectorProcessorThresholdFilterActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.THRESHOLD_FILTER]
    query: VectorInput = Field(..., description="Query vector.")
    candidates: VectorInput = Field(..., description="Flat list of candidate vectors.")
    threshold: Union[float, str] = Field(..., description="Score threshold. For similarity metrics, keep score >= threshold; for distance metrics, keep score <= threshold.")
    metric: RankingMetric = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric.")

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
