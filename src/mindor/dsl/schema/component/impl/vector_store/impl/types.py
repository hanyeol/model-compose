from enum import Enum

class VectorStoreDriver(str, Enum):
    MILVUS = "milvus"
