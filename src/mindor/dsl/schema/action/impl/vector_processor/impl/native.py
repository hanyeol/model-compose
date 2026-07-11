from typing import Union, Literal, Annotated
from pydantic import Field
from mindor.dsl.schema.common.vector import Vector, VectorList
from .common import CommonVectorProcessorActionConfig, VectorProcessorActionMethod, SimilarityMetric, DistanceMetric, RankingMetric

class VectorProcessorSimilarityActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SIMILARITY]
    vector: Union[Vector, str] = Field(..., description="Vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[SimilarityMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity metric.")

class VectorProcessorDistanceActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DISTANCE]
    vector: Union[Vector, str] = Field(..., description="Vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors to compare against. Broadcasts against `vector`.")
    metric: Union[DistanceMetric, str] = Field(default=DistanceMetric.EUCLIDEAN, description="Distance metric.")

class VectorProcessorDotProductActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.DOT_PRODUCT]
    vector: Union[Vector, str] = Field(..., description="Vector or batch of vectors.")
    other: Union[Vector, str] = Field(..., description="Vector or batch of vectors. Broadcasts against `vector`.")

class VectorProcessorNormalizeActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.NORMALIZE]
    vector: Union[Vector, str] = Field(..., description="Vector or batch of vectors to L2-normalize.")

class VectorProcessorMeanActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.MEAN]
    vectors: Union[VectorList, str] = Field(..., description="Vectors to average (list of vectors).")
    axis: Union[int, str] = Field(default=0, description="Axis along which to take the mean.")

class VectorProcessorSumActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.SUM]
    vectors: Union[VectorList, str] = Field(..., description="Vectors to sum (list of vectors).")
    axis: Union[int, str] = Field(default=0, description="Axis along which to sum.")

class VectorProcessorTopKActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.TOP_K]
    query: Union[Vector, str] = Field(..., description="Query vector.")
    candidates: Union[VectorList, str] = Field(..., description="Flat list of candidate vectors.")
    k: Union[int, str] = Field(default=1, description="Number of top matches to return.")
    metric: Union[RankingMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric.")

class VectorProcessorThresholdFilterActionConfig(CommonVectorProcessorActionConfig):
    method: Literal[VectorProcessorActionMethod.THRESHOLD_FILTER]
    query: Union[Vector, str] = Field(..., description="Query vector.")
    candidates: Union[VectorList, str] = Field(..., description="Flat list of candidate vectors.")
    threshold: Union[float, str] = Field(..., description="Score threshold. For similarity metrics, keep score >= threshold; for distance metrics, keep score <= threshold.")
    metric: Union[RankingMetric, str] = Field(default=SimilarityMetric.COSINE, description="Similarity or distance metric.")

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
