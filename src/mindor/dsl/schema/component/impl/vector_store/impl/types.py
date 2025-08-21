from enum import Enum

class VectorStoreDriver(str, Enum):
    MILVUS = "milvus"
    QDRANT = "qdrant"
    FAISS  = "faiss"
    CHROMA = "chroma"
