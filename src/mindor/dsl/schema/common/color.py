from typing import Union, Tuple, List

# A color value expressed as either a hex/name string (e.g. `"#ff0000"`,
# `"#00000000"`), an RGB 3-tuple, or an RGBA 4-tuple. Each driver decides how
# to interpret 3-tuple vs 4-tuple inputs (usually by defaulting alpha to 255).
Color = Union[
    str,
    Tuple[int, int, int],
    Tuple[int, int, int, int],
    List[int],
]
