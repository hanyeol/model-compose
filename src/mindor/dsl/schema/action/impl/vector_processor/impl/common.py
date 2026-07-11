from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class VectorProcessorActionMethod(str, Enum):
    COSINE_SIMILARITY   = "cosine-similarity"
    DOT_PRODUCT         = "dot-product"
    EUCLIDEAN_DISTANCE  = "euclidean-distance"
    NORMALIZE           = "normalize"
    MEAN                = "mean"
    SUM                 = "sum"
    TOP_K               = "top-k"
    THRESHOLD_FILTER    = "threshold-filter"

class VectorSimilarityMetric(str, Enum):
    COSINE    = "cosine"
    DOT       = "dot"
    EUCLIDEAN = "euclidean"

class CommonVectorProcessorActionConfig(CommonActionConfig):
    method: VectorProcessorActionMethod = Field(..., description="Vector processor method.")
