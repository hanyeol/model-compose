from typing import Union, Optional, Tuple, List

# A 4-tuple `(left, top, right, bottom)` describing a rectangular region on a
# 2-D surface (image frame, video frame, etc.). Any element may be `None` to
# leave that edge unspecified; each driver decides how to interpret a missing
# edge (e.g. "keep the source edge", "reject", etc.).
Box = Union[
    Tuple[Optional[int], Optional[int], Optional[int], Optional[int]],
    List[Optional[int]],
    str,
]
