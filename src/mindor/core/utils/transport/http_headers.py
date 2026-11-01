from typing import Any, Iterable, Mapping, Optional, Tuple, Union

class CaseInsensitiveDict(dict):
    """Dict with case-insensitive string keys. Non-string keys are stored as-is.

    Mirrors the subset of `requests.structures.CaseInsensitiveDict` that this
    codebase relies on (header lookup / update): all mutations and lookups
    normalize string keys to lowercase, so `d["Content-Type"]` and
    `d["content-type"]` refer to the same slot. Non-string keys pass through
    unchanged to keep sentinel/typed dict uses working.
    """
    def __init__(
        self,
        data: Optional[Union[Mapping[Any, Any], Iterable[Tuple[Any, Any]]]] = None,
    ) -> None:
        super().__init__()
        if data:
            self.update(data)

    def __getitem__(self, key: Any) -> Any:
        return super().__getitem__(self._normalize(key))

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(self._normalize(key), value)

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(self._normalize(key))

    def __contains__(self, key: Any) -> bool:
        return super().__contains__(self._normalize(key))

    def get(self, key: Any, default: Any = None) -> Any:
        return super().get(self._normalize(key), default)

    def pop(self, key: Any, *args: Any) -> Any:
        return super().pop(self._normalize(key), *args)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        return super().setdefault(self._normalize(key), default)

    def update(
        self,
        *args: Union[Mapping[Any, Any], Iterable[Tuple[Any, Any]]],
        **kwargs: Any,
    ) -> None:
        for source in args:
            if hasattr(source, "items"):
                source = source.items()

            for key, value in source:
                self[key] = value

        for key, value in kwargs.items():
            self[key] = value

    @staticmethod
    def _normalize(key: Any) -> Any:
        return key.lower() if isinstance(key, str) else key
