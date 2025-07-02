from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.utils.http_client import HttpClient
from .runner import ControllerClient
from starlette.datastructures import UploadFile

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

        if self._contains_upload_file(input):
            body = { key: value for key, value in self._flatten_for_multipart(body) }
            headers = {
                "Content-Type": "multipart/form-data"
            }

        return await self.client.request(url, method, None, body, headers)

    def _flatten_for_multipart(self, body: Dict[str, Any], key: str = "") -> List[Tuple[str, Any]]:
        flattened = []

        for subkey, value in body.items():
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
