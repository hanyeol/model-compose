from mindor.dsl.schema.component import ModelComponentConfig, PestoBackend

class PestoMusicPitchEstimationTaskDriver:
    """Backend dispatcher for the PESTO music pitch estimation family.

    The outer family dispatch in `custom.py` returns this class, which in
    turn instantiates the per-backend driver based on `component.backend`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.backend == PestoBackend.TORCH:
            from .backends.torch import PestoTorchMusicPitchEstimationTaskDriver
            return PestoTorchMusicPitchEstimationTaskDriver(id, config, daemon)

        if config.backend == PestoBackend.ONNX:
            from .backends.onnx import PestoOnnxMusicPitchEstimationTaskDriver
            return PestoOnnxMusicPitchEstimationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown backend: {config.backend}")
