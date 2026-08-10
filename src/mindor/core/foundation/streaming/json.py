from typing import Any
from .resources import StreamResource, read_stream_to_bytes
from .resolver import resolve_stream_resource
import asyncio, json

# Payloads at or above this size are offloaded to a worker thread so multi-MB
# JSON conversions don't stall the loop. `encode_json` can't cheaply predict
# output size without serializing, so it always offloads; `decode_json` uses
# input length.
_OFFLOAD_THRESHOLD_BYTES = 16 * 1024

async def encode_value_to_json(value: Any) -> str:
    if isinstance(value, str):
        return await encode_json(value)

    if isinstance(value, (bytes, bytearray)):
        return await encode_json(bytes(value).decode("utf-8"))

    if isinstance(value, StreamResource):
        return await encode_stream_to_json(value)

    return await encode_json(value)

async def encode_stream_to_json(stream: StreamResource) -> str:
    data = (await read_stream_to_bytes(stream)).decode("utf-8")
    return await encode_json(data)

async def encode_json(value: Any) -> str:
    return await asyncio.to_thread(lambda: json.dumps(value, ensure_ascii=False, default=str))

async def decode_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return await decode_json(value)

    if isinstance(value, (bytes, bytearray)):
        return await decode_json(bytes(value).decode("utf-8"))

    if isinstance(value, (dict, list)):
        return value

    if not isinstance(value, StreamResource):
        value = await resolve_stream_resource(value)

    return await decode_json_stream(value)

async def decode_json_stream(stream: StreamResource) -> Any:
    return await decode_json((await read_stream_to_bytes(stream)).decode("utf-8"))

async def decode_json(data: str) -> Any:
    if len(data) < _OFFLOAD_THRESHOLD_BYTES:
        return json.loads(data)

    return await asyncio.to_thread(json.loads, data)
