from typing import Optional, Tuple, Union, Any

Color = Tuple[int, int, int, int]

class ColorValueRenderer:
    async def render(self, value: Any, default: Optional[Color] = None) -> Optional[Color]:
        if isinstance(value, (str, list, tuple)):
            return parse_color(value)

        return default

def parse_color(value: Union[str, list, tuple]) -> Color:
    if isinstance(value, (list, tuple)):
        channels = [ int(channel) for channel in value ]

        if len(channels) == 3:
            return (channels[0], channels[1], channels[2], 255)

        if len(channels) == 4:
            return (channels[0], channels[1], channels[2], channels[3])

        raise ValueError(f"Color tuple must have 3 or 4 channels: {value}")

    if isinstance(value, str):
        text = value.strip().lstrip("#")

        if len(text) == 6:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 255)

        if len(text) == 8:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), int(text[6:8], 16))

        if len(text) == 3:
            return (int(text[0] * 2, 16), int(text[1] * 2, 16), int(text[2] * 2, 16), 255)

        raise ValueError(f"Invalid hex color: {value}")

    raise ValueError(f"Unsupported color value: {value}")
