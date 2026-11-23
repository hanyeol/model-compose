from mindor.dsl.schema.component import ModelComponentConfig, MinimaxH3ImageGenerationBackend

class MinimaxH3ImageGenerationTaskDriver:
    """Backend dispatcher for the MiniMax-H3 image generation family.

    The outer family dispatch in `custom.py` returns this class, which in
    turn instantiates the per-backend driver based on `component.backend`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.backend == MinimaxH3ImageGenerationBackend.SOL:
            from .backends.sol import MinimaxH3SolImageGenerationTaskDriver
            return MinimaxH3SolImageGenerationTaskDriver(id, config, daemon)

        from .backends.torch import MinimaxH3TorchImageGenerationTaskDriver
        return MinimaxH3TorchImageGenerationTaskDriver(id, config, daemon)
