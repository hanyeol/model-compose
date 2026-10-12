"""Schema tests for the image-processor OpenCV driver and Canny action."""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    ImageProcessorComponentConfig,
    OpenCvImageProcessorComponentConfig,
    ImageProcessorDriverType,
)
from mindor.dsl.schema.action import (
    OpenCvImageProcessorActionConfig,
    OpenCvImageProcessorCannyActionConfig,
    OpenCvImageProcessorActionMethod,
)


COMPONENT_ADAPTER = TypeAdapter(ImageProcessorComponentConfig)
ACTION_ADAPTER = TypeAdapter(OpenCvImageProcessorActionConfig)


class TestOpenCvDiscriminator:
    def test_driver_opencv_resolves_to_opencv_component(self):
        cfg = COMPONENT_ADAPTER.validate_python({
            "type": "image-processor",
            "driver": "opencv",
            "actions": [{"method": "canny", "image": "${input.image}"}],
        })
        assert isinstance(cfg, OpenCvImageProcessorComponentConfig)
        assert cfg.driver == ImageProcessorDriverType.OPENCV

    def test_native_method_rejected_on_opencv_driver(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python({
                "type": "image-processor",
                "driver": "opencv",
                "actions": [{"method": "resize", "image": "${input.image}", "width": 100}],
            })

    def test_opencv_method_rejected_on_native_driver(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python({
                "type": "image-processor",
                "driver": "native",
                "actions": [{"method": "canny", "image": "${input.image}"}],
            })


class TestCannyActionDefaults:
    def test_default_thresholds(self):
        action = ACTION_ADAPTER.validate_python({
            "method": "canny",
            "image": "${input.image}",
        })
        assert isinstance(action, OpenCvImageProcessorCannyActionConfig)
        assert action.method == OpenCvImageProcessorActionMethod.CANNY
        assert action.low_threshold == 100
        assert action.high_threshold == 200

    def test_threshold_override(self):
        action = ACTION_ADAPTER.validate_python({
            "method": "canny",
            "image": "${input.image}",
            "low_threshold": 50,
            "high_threshold": 150,
        })
        assert action.low_threshold == 50
        assert action.high_threshold == 150

    def test_variable_expressions_accepted(self):
        action = ACTION_ADAPTER.validate_python({
            "method": "canny",
            "image": "${input.image}",
            "low_threshold": "${input.low | 80}",
            "high_threshold": "${input.high | 180}",
        })
        assert action.low_threshold == "${input.low | 80}"
        assert action.high_threshold == "${input.high | 180}"
