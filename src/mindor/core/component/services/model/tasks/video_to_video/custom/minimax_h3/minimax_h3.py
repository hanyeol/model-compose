from mindor.dsl.schema.component import ModelComponentConfig, MinimaxH3VideoToVideoBackend

class MinimaxH3VideoToVideoTaskDriver:
    """Backend dispatcher for the MiniMax-H3 video-to-video (ref2va) family.

    The outer family dispatch in `custom.py` returns this class, which in
    turn instantiates the per-backend driver based on `component.backend`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.backend == MinimaxH3VideoToVideoBackend.SOL:
            from .backends.sol import MinimaxH3SolVideoToVideoTaskDriver
            return MinimaxH3SolVideoToVideoTaskDriver(id, config, daemon)

        from .backends.torch import MinimaxH3TorchVideoToVideoTaskDriver
        return MinimaxH3TorchVideoToVideoTaskDriver(id, config, daemon)
