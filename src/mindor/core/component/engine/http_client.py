from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from mindor.dsl.schema.component import HttpClientComponentConfig
from mindor.dsl.schema.action import ActionConfig, HttpClientActionConfig, HttpClientCompletionConfig
from mindor.core.listener import HttpCallbackListener
from mindor.core.utils.http_client import HttpClient
from mindor.core.utils.time import parse_duration
from .base import ComponentEngine, ComponentType, ComponentEngineMap
from .context import ComponentContext
from datetime import datetime, timezone
import asyncio

class HttpClientPollingCompletion:
    def __init__(self, base_url: Optional[str], headers: Optional[Dict[str, str]], config: HttpClientCompletionConfig):
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.config: HttpClientCompletionConfig = config
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
            response = await self.client.request(url, method, params, body, headers)
            context.register_source("result", response)

            status = (await context.render_template(self.config.status)) if self.config.status else response["status"]

            if not status:
                raise RuntimeError(f"Polling failed: no status found in response.")

            for success_when in self.config.success_when if self.config.success_when else [ "completed" ]:
                if status == await context.render_template(success_when):
                    return response

            for fail_when in self.config.fail_when if self.config.fail_when else [ "failed" ]:
                if status == await context.render_template(fail_when):
                    raise RuntimeError(f"Polling failed: status '{status}' matched a failure condition.")

            await asyncio.sleep(interval.total_seconds())

        raise TimeoutError(f"Polling timed out after {timeout}.")

    async def _resolve_request_url(self, context: ComponentContext) -> str:
        if self.base_url and self.config.path:
            return await context.render_template(self.base_url) + await context.render_template(self.config.path)

        return await context.render_template(self.config.endpoint)

class HttpClientCallbackCompletion:
    def __init__(self, config: HttpClientCompletionConfig):
        self.config: HttpClientCompletionConfig = config

    async def run(self, context: ComponentContext) -> Any:
        callback_id = await context.render_template(self.config.wait_for)
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        HttpCallbackListener.register_pending_future(callback_id, future)

        return await future

class HttpClientAction:
    def __init__(self, base_url: Optional[str], headers: Optional[Dict[str, str]], config: HttpClientActionConfig):
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.config: HttpClientActionConfig = config
        self.client: HttpClient = HttpClient()

    async def run(self, context: ComponentContext) -> Any:
        url     = await self._resolve_request_url(context)
        method  = await context.render_template(self.config.method)
        params  = await context.render_template(self.config.params)
        body    = await context.render_template(self.config.body)
        headers = await context.render_template({ **self.headers, **self.config.headers })

        response, result = await self.client.request(url, method, params, body, headers), None
        context.register_source("response", response)

        if self.config.completion:
            result = await self._handle_completion(self.config.completion, context)
            context.register_source("result", result)

        return (await context.render_template(self.config.output)) if self.config.output else (result or response)

    async def _resolve_request_url(self, context: ComponentContext) -> str:
        if self.base_url and self.config.path:
            return await context.render_template(self.base_url) + await context.render_template(self.config.path)

        return await context.render_template(self.config.endpoint)

    async def _handle_completion(self, completion: HttpClientCompletionConfig, context: ComponentContext) -> Any:
        if completion.type == "polling":
            return await HttpClientPollingCompletion(self.base_url, self.headers, completion).run(context)
        
        if completion.type == "callback":
            return await HttpClientCallbackCompletion(completion).run(context)

        return None

class HttpClientComponent(ComponentEngine):
    def __init__(self, id: str, config: HttpClientComponentConfig, env: Dict[str, str], daemon: bool):
        super().__init__(id, config, env, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentContext) -> Any:
        return await HttpClientAction(self.config.base_url, self.config.headers, action).run(context)

ComponentEngineMap[ComponentType.HTTP_CLIENT] = HttpClientComponent
