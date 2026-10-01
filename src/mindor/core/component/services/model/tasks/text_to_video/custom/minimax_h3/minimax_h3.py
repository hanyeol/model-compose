from mindor.dsl.schema.component import ModelComponentConfig, MinimaxH3Backend

class MinimaxH3TextToVideoTaskDriver:
    """Backend dispatcher for the MiniMax-H3 text-to-video family.

    The outer family dispatch in `custom.py` returns this class, which in
    turn instantiates the per-backend driver based on `component.backend`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.backend == MinimaxH3Backend.SOL:
            from .backends.sol import MinimaxH3SolTextToVideoTaskDriver
            return MinimaxH3SolTextToVideoTaskDriver(id, config, daemon)

        from .backends.torch import MinimaxH3TorchTextToVideoTaskDriver
        return MinimaxH3TorchTextToVideoTaskDriver(id, config, daemon)
