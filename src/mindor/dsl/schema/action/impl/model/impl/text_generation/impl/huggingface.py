from enum import Enum

class HuggingfaceTextGenerationModelArchitecture(str, Enum):
    CAUSAL  = "causal"
    SEQ2SEQ = "seq2seq"
