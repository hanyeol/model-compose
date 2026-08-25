from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.common.vector import Vector, VectorList
from ...common import CommonActionConfig

class VectorProcessorActionMethod(str, Enum):
    # Pairwise vector operations (vector, other)
    SIMILARITY        = "similarity"
    DISTANCE          = "distance"
    DOT_PRODUCT       = "dot-product"
    # Ranking / filtering built on top of similarity or distance
    TOP_K             = "top-k"
    THRESHOLD_FILTER  = "threshold-filter"
    # Unary vector operations (vector)
    NORMALIZE         = "normalize"
    # Aggregation over a vector array (vectors)
    MEAN              = "mean"
    SUM               = "sum"

class SimilarityMetric(str, Enum):
    COSINE = "cosine"

class DistanceMetric(str, Enum):
    EUCLIDEAN = "euclidean"

# For ranking (top-k / threshold-filter) the metric may be either a similarity
# or a distance measure; sign convention (higher-is-better vs lower-is-better)
# is decided by which enum the value belongs to.
RankingMetric = Union[ SimilarityMetric, DistanceMetric ]

class CommonVectorProcessorActionConfig(CommonActionConfig):
    method: VectorProcessorActionMethod = Field(..., description="Vector processing operation this action performs.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input vectors processed per batch.")

class VectorProcessorSimilarityActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SIMILARITY]
    vector: Union[Vector, str] = Field(..., description="Input vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[SimilarityMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity metric applied to the vector pair.")

class VectorProcessorDistanceActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DISTANCE]
    vector: Union[Vector, str] = Field(..., description="Input vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[DistanceMetric, str] = Field(default=DistanceMetric.EUCLIDEAN, description="Distance metric applied to the vector pair.")

class VectorProcessorDotProductActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DOT_PRODUCT]
    vector: Union[Vector, str] = Field(..., description="Input vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors. Broadcasts against `vector`.")

class VectorProcessorNormalizeActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.NORMALIZE]
    vector: Union[Vector, str] = Field(..., description="Input vector or batch of vectors to L2-normalize.")

class VectorProcessorMeanActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.MEAN]
    vectors: Union[VectorList, str] = Field(..., description="Vectors to average.")
    axis: Union[int, str] = Field(default=0, description="Axis along which the mean is taken.")

class VectorProcessorSumActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SUM]
    vectors: Union[VectorList, str] = Field(..., description="Vectors to sum.")
    axis: Union[int, str] = Field(default=0, description="Axis along which the sum is taken.")

class VectorProcessorTopKActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.TOP_K]
    query: Union[Vector, str] = Field(..., description="Query vector ranked against the candidates.")
    candidates: Union[VectorList, str] = Field(..., description="Candidate vectors compared against the query.")
    k: Union[int, str] = Field(default=1, description="Number of top-ranked candidates returned.")
    metric: Union[RankingMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric used to rank candidates.")

class VectorProcessorThresholdFilterActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.THRESHOLD_FILTER]
    query: Union[Vector, str] = Field(..., description="Query vector ranked against the candidates.")
    candidates: Union[VectorList, str] = Field(..., description="Candidate vectors compared against the query.")
    threshold: Union[float, str] = Field(..., description="Score threshold candidates must clear to pass the filter.")
    metric: Union[RankingMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric used to score candidates.")
