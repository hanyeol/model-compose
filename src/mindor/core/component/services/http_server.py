from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import HttpServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, HttpServerActionConfig, HttpServerCompletionType, HttpServerCompletionConfig
from mindor.dsl.schema.transport.http import HttpStreamFormat
from mindor.core.listener import HttpCallbackListener
from mindor.core.utils.http_client import HttpClient
from mindor.core.utils.http_status import is_status_code_matched
from mindor.core.utils.streaming import StreamResource
from mindor.core.utils.time import parse_duration
from mindor.core.utils.shell import run_command_foreground
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from datetime import datetime, timezone
import asyncio, json

class HttpServerCompletion(ABC):
    def __init__(self, config: HttpServerCompletionConfig):
        self.config: HttpServerCompletionConfig = config

    @abstractmethod
    async def run(self, context: ComponentActionContext, client: HttpClient, streaming: bool = False) -> Any:
        pass

class HttpServerPollingCompletion(HttpServerCompletion):
    async def run(self, context: ComponentActionContext, client: HttpClient, streaming: bool = False) -> Any:
        path    = await context.render_variable(self.config.path)
        method  = await context.render_variable(self.config.method)
        params  = await context.render_variable(self.config.params)
        body    = await context.render_variable(self.config.body)
        headers = await context.render_variable(self.config.headers)

        interval = parse_duration((await context.render_variable(self.config.interval)) or 5.0)
        timeout  = parse_duration((await context.render_variable(self.config.timeout)) or 300.0)
        deadline = datetime.now(timezone.utc) + timeout

        await asyncio.sleep(interval.total_seconds())

        while datetime.now(timezone.utc) < deadline:
            response, status_code = await client.request(path or "", method, params, body, headers, raise_on_error=False, streaming=streaming)
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

class HttpServerCallbackCompletion(HttpServerCompletion):
    async def run(self, context: ComponentActionContext, client: HttpClient, streaming: bool = False) -> Any:
        callback_id = await context.render_variable(self.config.wait_for) if self.config.wait_for else "__callback__"
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        HttpCallbackListener.register_pending_future(callback_id, future)

        return await future

class HttpServerAction:
    def __init__(self, config: HttpServerActionConfig):
        self.config: HttpServerActionConfig = config
        self.completion: HttpServerCompletion = None

        if self.config.completion:
            self._configure_completion()

    def _configure_completion(self) -> None:
        if self.config.completion.type == HttpServerCompletionType.POLLING:
            self.completion = HttpServerPollingCompletion(self.config.completion)
            return
        
        if self.config.completion.type == HttpServerCompletionType.CALLBACK:
            self.completion = HttpServerCallbackCompletion(self.config.completion)
            return
        
        raise ValueError(f"Unsupported http completion type: {self.config.completion.type}")

    async def run(self, context: ComponentActionContext, client: HttpClient) -> Any:
        path    = await context.render_variable(self.config.path)
        method  = await context.render_variable(self.config.method)
        params  = await context.render_variable(self.config.params)
        body    = await context.render_variable(self.config.body)
        headers = await context.render_variable(self.config.headers)

        is_streaming = context.contains_variable_reference("response[]", self.config.output)
        response, result = await client.request(path or "", method, params, body, headers, streaming=is_streaming), None

        if isinstance(response, StreamResource) and is_streaming:
            async def _stream_output_generator(stream: StreamResource):
                async for chunk in stream:
                    context.register_source("response[]", self._convert_stream_chunk(chunk, self.config.stream_format))
                    chunk = await context.render_variable(self.config.output, convert_media=False)
                    if chunk is not None:
                        yield chunk

            return _stream_output_generator(response)

        context.register_source("response", response)

        if self.completion:
            is_streaming = context.contains_variable_reference("result[]", self.config.output)
            result = await self.completion.run(context, client, streaming=is_streaming)

            if isinstance(result, StreamResource) and is_streaming:
                async def _stream_output_generator(stream: StreamResource):
                    async for chunk in stream:
                        context.register_source("result[]", self._convert_stream_chunk(chunk, self.config.stream_format))
                        chunk = await context.render_variable(self.config.output, convert_media=False)
                        if chunk is not None:
                            yield chunk

                return _stream_output_generator(result)

            context.register_source("result", result)

        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else (result or response)

    def _convert_stream_chunk(self, chunk: bytes, format: HttpStreamFormat) -> Any:
        if format == HttpStreamFormat.JSON:
            try:
                return json.loads(chunk)
            except:
                return None

        if format == HttpStreamFormat.TEXT:
            return chunk.decode("utf-8", errors="replace")

        return chunk

@register_component(ComponentType.HTTP_SERVER)
class HttpServerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: HttpServerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.client: Optional[HttpClient] = None

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

        if self.config.manage.scripts.build:
            for command in self.config.manage.scripts.build:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _start(self) -> None:
        base_url = f"http://localhost:{self.config.port}" + (self.config.base_path or "")
        self.client = HttpClient(base_url, self.config.headers)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.client.close()
        self.client = None

    async def _serve(self) -> None:
        if self.config.manage.scripts.start:
            await run_command_foreground(self.config.manage.scripts.start, self.config.manage.working_dir, self.config.manage.env)

    async def _is_ready(self) -> bool:
        try:
            _, writer = await asyncio.open_connection("localhost", self.config.port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            return False

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await HttpServerAction(action).run(context, self.client)
