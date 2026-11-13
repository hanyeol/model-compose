from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceTextEmbeddingModelArchitecture
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_EMBEDDING, ModelDriverType.HUGGINGFACE)
class HuggingfaceTextEmbeddingTaskDriver:
    """Architecture dispatcher for the HuggingFace text-embedding driver.

    SBERT follows a different load path (SentenceTransformer loader, no
    tokenizer), so it gets its own driver. Every other architecture (BERT,
    CLIP, SigLIP, XCLIP, AUTO) shares the common transformers loader path.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.architecture == HuggingfaceTextEmbeddingModelArchitecture.SBERT:
            from .architectures.sbert import SbertHuggingfaceTextEmbeddingTaskDriver
            return SbertHuggingfaceTextEmbeddingTaskDriver(id, config, daemon)

        from .architectures.general import GeneralHuggingfaceTextEmbeddingTaskDriver
        return GeneralHuggingfaceTextEmbeddingTaskDriver(id, config, daemon)
