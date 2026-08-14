from typing import Union, Literal, Annotated
from pydantic import Field
from mindor.dsl.schema.common.vector import Vector, VectorList
from .common import CommonVectorProcessorActionConfig, VectorProcessorActionMethod, SimilarityMetric, DistanceMetric, RankingMetric

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
