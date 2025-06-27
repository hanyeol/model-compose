from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.utils.http_client import HttpClient
from .runner import ControllerClient

class HttpControllerClient(ControllerClient):
    def __init__(self, config: ControllerConfig):
        super().__init__(config)

        self.client: HttpClient = HttpClient()

    async def run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        base_path = self.config.base_path if self.config.base_path else ""
        url = f"http://localhost:{self.config.port}{base_path}/workflows"
        method = "POST"
        body = {
            "workflow_id": workflow_id,
            "input": input,
            "wait_for_completion": True,
            "output_only": True
        }
        headers = {
            "Content-Type": "application/json"
        }

        return await self.client.request(url, method, None, body, headers)
