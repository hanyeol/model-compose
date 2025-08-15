from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, AsyncIterable, Any
import json

class HttpEventStreamer:
    def __init__(self, iterator: AsyncIterable[Any]):
        self.iterator: AsyncIterable[Any] = iterator

    async def stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.iterator:
            if not isinstance(chunk, (str, bytes)):
                if chunk is None:
                    continue
                chunk = json.dumps(chunk, ensure_ascii=False, default=str)
            
            if isinstance(chunk, str):
                if chunk.endswith("\n"):
                    lines = chunk.split("\n")
                    if chunk.startswith("\n"):
                        lines = lines[1:]
                    chunk = [ line.encode("utf-8") for line in lines ]
                else:
                    chunk = chunk.encode("utf-8")

            for line in [ chunk ] if isinstance(chunk, bytes) else chunk:
                yield b"data: " + line + b"\n"

            yield b"\n"
