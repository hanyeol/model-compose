from mindor.dsl.schema.component import ModelComponentConfig, MinimaxH3ImageToVideoBackend

class MinimaxH3ImageToVideoTaskDriver:
    """Backend dispatcher for the MiniMax-H3 image-to-video family.

    The outer family dispatch in `custom.py` returns this class, which in
    turn instantiates the per-backend driver based on `component.backend`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.backend == MinimaxH3ImageToVideoBackend.SOL:
            from .backends.sol import MinimaxH3SolImageToVideoTaskDriver
            return MinimaxH3SolImageToVideoTaskDriver(id, config, daemon)

        from .backends.torch import MinimaxH3TorchImageToVideoTaskDriver
        return MinimaxH3TorchImageToVideoTaskDriver(id, config, daemon)
