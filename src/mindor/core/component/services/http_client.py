from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import HttpClientComponentConfig
from mindor.dsl.schema.action import ActionConfig, HttpClientActionConfig, HttpClientCompletionType, HttpClientCompletionConfig
from mindor.dsl.schema.transport.http import HttpStreamFormat
from mindor.core.listener import HttpCallbackListener
from mindor.core.utils.http_client import HttpClient, HttpEventStreamResource
from mindor.core.utils.http_status import is_status_code_matched
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from datetime import datetime, timezone
import asyncio, json

class HttpClientCompletion(ABC):
    def __init__(self, config: HttpClientCompletionConfig):
        self.config: HttpClientCompletionConfig = config

    @abstractmethod
    async def run(self, context: ComponentActionContext, client: HttpClient) -> Any:
        pass

class HttpClientPollingCompletion(HttpClientCompletion):
    async def run(self, context: ComponentActionContext, client: HttpClient) -> Any:
        url_or_path = await self._resolve_url_or_path(context)
        method      = await context.render_variable(self.config.method)
        params      = await context.render_variable(self.config.params)
        body        = await context.render_variable(self.config.body)
        headers     = await context.render_variable(self.config.headers)

        interval = parse_duration((await context.render_variable(self.config.interval)) or 5.0)
        timeout  = parse_duration((await context.render_variable(self.config.timeout)) or 300.0)
        deadline = datetime.now(timezone.utc) + timeout

        await asyncio.sleep(interval.total_seconds())

        while datetime.now(timezone.utc) < deadline:
            response, status_code = await client.request(url_or_path, method, params, body, headers, raise_on_error=False)
            context.register_source("result", response)

            status = (await context.render_variable(self.config.status)) if self.config.status else None
            if status:
                if status in (self.config.success_when or []):
                    return response
                if status in (self.config.fail_when or []):
                    raise RuntimeError(f"Polling failed: status '{status}' matched a failure condition.")
            else: # use status code
                if is_status_code_matched(status_code, self.config.success_when or []):
                    return response
                if is_status_code_matched(status_code, self.config.fail_when or []):
                    raise RuntimeError(f"Polling failed: status code '{status_code}' matched a failure condition.")

            await asyncio.sleep(interval.total_seconds())

        raise TimeoutError(f"Polling timed out after {timeout}.")

    async def _resolve_url_or_path(self, context: ComponentActionContext) -> str:
        if self.config.path:
            return await context.render_variable(self.config.path)

        return await context.render_variable(self.config.endpoint)

class HttpClientCallbackCompletion(HttpClientCompletion):
    async def run(self, context: ComponentActionContext, client: HttpClient) -> Any:
        callback_id = await context.render_variable(self.config.wait_for)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        HttpCallbackListener.register_pending_future(callback_id, future)

        return await future

class HttpClientAction:
    def __init__(self, config: HttpClientActionConfig):
        self.config: HttpClientActionConfig = config
        self.completion: HttpClientCompletion = None

        if self.config.completion:
            self._configure_completion()

    def _configure_completion(self) -> None:
        if self.config.completion.type == HttpClientCompletionType.POLLING:
            self.completion = HttpClientPollingCompletion(self.config.completion)
            return
        
        if self.config.completion.type == HttpClientCompletionType.CALLBACK:
            self.completion = HttpClientCallbackCompletion(self.config.completion)
            return
        
        raise ValueError(f"Unsupported http completion type: {self.config.completion.type}")

    async def run(self, context: ComponentActionContext, client: HttpClient) -> Any:
        url_or_path = await self._resolve_url_or_path(context)
        method      = await context.render_variable(self.config.method)
        params      = await context.render_variable(self.config.params)
        body        = await context.render_variable(self.config.body)
        headers     = await context.render_variable(self.config.headers)

        response, result = await client.request(url_or_path, method, params, body, headers), None

        if isinstance(response, HttpEventStreamResource) and context.contains_variable_reference("response[]", self.config.output):
            async def _stream_generator(stream: HttpEventStreamResource):
                async for chunk in stream:
                    context.register_source("response[]", self._convert_stream_chunk(chunk))
                    yield await context.render_variable(self.config.output, ignore_files=True)

            return _stream_generator(response)

        context.register_source("response", response)

        if self.completion:
            result = await self.completion.run(context, client)

            if isinstance(result, HttpEventStreamResource) and context.contains_variable_reference("result[]", self.config.output):
                async def _stream_generator(stream: HttpEventStreamResource):
                    async for chunk in stream:
                        context.register_source("result[]", self._convert_stream_chunk(chunk))
                        yield await context.render_variable(self.config.output, ignore_files=True)

                return _stream_generator(result)

            context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else (result or response)

    async def _resolve_url_or_path(self, context: ComponentActionContext) -> str:
        if self.config.path:
            return await context.render_variable(self.config.path)

        return await context.render_variable(self.config.endpoint)

    def _convert_stream_chunk(self, chunk: bytes) -> Any:
        if self.config.stream_format == HttpStreamFormat.JSON:
            try:
                return json.loads(chunk)
            except:
                return None

        if self.config.stream_format == HttpStreamFormat.TEXT:
            return chunk.decode("utf-8", errors="replace")

        return chunk

@register_component(ComponentType.HTTP_CLIENT)
class HttpClientComponent(ComponentService):
    def __init__(self, id: str, config: HttpClientComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.client: Optional[HttpClient] = None

    async def _start(self) -> None:
        self.client = HttpClient(self.config.base_url, self.config.headers)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.client.close()
        self.client = None

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await HttpClientAction(action).run(context, self.client)
