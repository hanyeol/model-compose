from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import HttpClientComponentConfig
from mindor.dsl.schema.action import ActionConfig, HttpClientActionConfig, HttpClientCompletionConfig
from mindor.core.listener import HttpCallbackListener
from mindor.core.utils.http_client import HttpClient
from mindor.core.utils.http_status import is_status_code_matched
from mindor.core.utils.time import parse_duration
from .base import ComponentEngine, ComponentType, ComponentEngineMap
from .context import ComponentContext
from datetime import datetime, timezone
import asyncio

class HttpClientCompletion(ABC):
    @abstractmethod
    async def run(self, context: ComponentContext) -> Any:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class HttpClientPollingCompletion(HttpClientCompletion):
    def __init__(self, config: HttpClientCompletionConfig, base_url: Optional[str], headers: Optional[Dict[str, str]]):
        self.config: HttpClientCompletionConfig = config
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.client: HttpClient = HttpClient()

    async def run(self, context: ComponentContext) -> Any:
        url     = await self._resolve_request_url(context)
        method  = await context.render_template(self.config.method)
        params  = await context.render_template(self.config.params)
        body    = await context.render_template(self.config.body)
        headers = await context.render_template({ **self.headers, **self.config.headers })

        interval = parse_duration(self.config.interval) if self.config.interval else 5.0
        timeout  = parse_duration(self.config.timeout) if self.config.timeout else 300
        deadline = datetime.now(timezone.utc) + timeout

        await asyncio.sleep(interval.total_seconds())

        while datetime.now(timezone.utc) < deadline:
            response, status_code = await self.client.request(url, method, params, body, headers, raise_on_error=False)
            context.register_source("result", response)

            status = (await context.render_template(self.config.status)) if self.config.status else None
            if self.config.status and not status:
                raise RuntimeError(f"Polling failed: no status found in response.")

            if status:
                if status in self.config.success_when or []:
                    return response
                if status in self.config.fail_when or []:
                    raise RuntimeError(f"Polling failed: status '{status}' matched a failure condition.")
            else: # use status code
                if is_status_code_matched(status_code, self.config.success_when or []):
                    return response
                if is_status_code_matched(status_code, self.config.fail_when or []):
                    raise RuntimeError(f"Polling failed: status code '{status_code}' matched a failure condition.")

            await asyncio.sleep(interval.total_seconds())

        raise TimeoutError(f"Polling timed out after {timeout}.")

    async def close(self) -> None:
        await self.client.close()

    async def _resolve_request_url(self, context: ComponentContext) -> str:
        if self.base_url and self.config.path:
            return await context.render_template(self.base_url) + await context.render_template(self.config.path)

        return await context.render_template(self.config.endpoint)

class HttpClientCallbackCompletion(HttpClientCompletion):
    def __init__(self, config: HttpClientCompletionConfig):
        self.config: HttpClientCompletionConfig = config

    async def run(self, context: ComponentContext) -> Any:
        callback_id = await context.render_template(self.config.wait_for)
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        HttpCallbackListener.register_pending_future(callback_id, future)

        return await future
    
    async def close(self) -> None:
        pass

class HttpClientAction:
    def __init__(self, config: HttpClientActionConfig, base_url: Optional[str], headers: Optional[Dict[str, str]]):
        self.config: HttpClientActionConfig = config
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.completion: HttpClientCompletion = None

        if self.config.completion:
            self._configure_completion()

    def _configure_completion(self) -> None:
        if self.config.completion.type == "polling":
            self.completion = HttpClientPollingCompletion(self.config.completion, self.base_url, self.headers)
            return
        
        if self.config.completion.type == "callback":
            self.completion = HttpClientCallbackCompletion(self.config.completion)
            return
        
        raise ValueError(f"Unsupported http completion type: {self.config.completion.type}")

    async def run(self, context: ComponentContext, client: HttpClient) -> Any:
        url     = await self._resolve_request_url(context)
        method  = await context.render_template(self.config.method)
        params  = await context.render_template(self.config.params)
        body    = await context.render_template(self.config.body)
        headers = await context.render_template({ **self.headers, **self.config.headers })

        response, result = await client.request(url, method, params, body, headers), None
        context.register_source("response", response)

        if self.completion:
            result = await self.completion.run(context)
            context.register_source("result", result)

        return (await context.render_template(self.config.output, ignore_files=True)) if self.config.output else (result or response)

    async def close(self) -> None:
        if self.completion:
            await self.completion.close()

    async def _resolve_request_url(self, context: ComponentContext) -> str:
        if self.base_url and self.config.path:
            return await context.render_template(self.base_url) + await context.render_template(self.config.path)

        return await context.render_template(self.config.endpoint)

class HttpClientComponent(ComponentEngine):
    def __init__(self, id: str, config: HttpClientComponentConfig, env: Dict[str, str], daemon: bool):
        super().__init__(id, config, env, daemon)

        self.client: HttpClient = None

    async def _serve(self) -> None:
        self.client = HttpClient()

    async def _shutdown(self) -> None:
        await self.client.close()
        self.client = None

    async def _run(self, action: ActionConfig, context: ComponentContext) -> Any:
        return await HttpClientAction(action, self.config.base_url, self.config.headers).run(context, self.client)

ComponentEngineMap[ComponentType.HTTP_CLIENT] = HttpClientComponent
