from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.utils.http_client import HttpClient
from .client import ControllerClient
from starlette.datastructures import UploadFile

class HttpControllerClient(ControllerClient):
    def __init__(self, config: ControllerConfig):
        super().__init__(config)

        self.client: HttpClient = HttpClient(self._resolve_controller_url())

    async def run_workflow(self, workflow_id: Optional[str], input: Any, workflow: WorkflowSchema) -> Any:
        body = {
            "workflow_id": workflow_id,
            "input": input,
            "wait_for_completion": True,
            "output_only": True
        }
        headers = {
            "Content-Type": "application/json"
        }

        if self._contains_upload_file(input):
            body = { key: value for key, value in self._flatten_for_multipart(body) }
            headers = {
                "Content-Type": "multipart/form-data"
            }

        return await self.client.request("/workflows", "POST", None, body, headers)

    async def close(self) -> None:
        await self.client.close()

    def _resolve_controller_url(self) -> str:
        return f"http://localhost:{self.config.port}" + (self.config.base_path or "")
    
    def _flatten_for_multipart(self, data: Dict[str, Any], key: str = "") -> List[Tuple[str, Any]]:
        flattened = []

        for subkey, value in data.items():
            full_key = f"{key}[{subkey}]" if key else subkey

            if isinstance(value, dict):
                flattened.extend(self._flatten_for_multipart(value, full_key))
                continue

            if isinstance(value, list):
                for item in value:
                    list_key = f"{full_key}[]"
                    if isinstance(item, (dict, list)):
                        flattened.extend(self._flatten_for_multipart({ list_key: item }))
                    else:
                        flattened.append((list_key, item))
                continue

            if value is not None:
                flattened.append((full_key, value))

        return flattened

    def _contains_upload_file(self, value: Any) -> bool:
        if isinstance(value, UploadFile):
            return True
        
        if isinstance(value, dict):
            return any(self._contains_upload_file(v) for v in value.values())
        
        if isinstance(value, list):
            return any(self._contains_upload_file(v) for v in value)
        
        return False
