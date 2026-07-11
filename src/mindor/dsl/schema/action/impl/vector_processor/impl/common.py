from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class VectorProcessorActionMethod(str, Enum):
    # Similarity / distance (higher-is-closer vs lower-is-closer)
    SIMILARITY        = "similarity"
    DISTANCE          = "distance"
    # Ranking / filtering built on top of similarity or distance
    TOP_K             = "top-k"
    THRESHOLD_FILTER  = "threshold-filter"
    # Pure vector operations
    DOT_PRODUCT       = "dot-product"
    NORMALIZE         = "normalize"
    MEAN              = "mean"
    SUM               = "sum"

class SimilarityMetric(str, Enum):
    COSINE = "cosine"

class DistanceMetric(str, Enum):
    EUCLIDEAN = "euclidean"

class CommonVectorProcessorActionConfig(CommonActionConfig):
    method: VectorProcessorActionMethod = Field(..., description="Vector processor method.")
