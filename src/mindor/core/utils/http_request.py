from typing import Dict, List, Tuple, Optional, Any
from requests.structures import CaseInsensitiveDict
from starlette.datastructures import FormData, UploadFile
from urllib.parse import urlencode
from fastapi import Request
import aiohttp, re, json, os

_token_pattern = r"([\w!#$%&'*+\-.^_`|~]+)"
_quoted_pattern = r'"([^"]*)"'
_option_regex = re.compile(fr";\s*{_token_pattern}=(?:{_token_pattern}|{_quoted_pattern})", re.ASCII)
_firefox_escape_fix_regex = re.compile(r'\\"(?!; |\s*$)')
_nested_key_regex = re.compile(r"\w+\[\]|\w+|\[\w+\]")

class NestedFormParser:
    def parse(self, form: FormData) -> dict:
        data = {}

        for form_key, value in form.items():
            keys, current = self._parse_key_path(form_key), data
            for index, key in enumerate(keys):
                if index == len(keys) - 1:
                    if key.endswith("[]"):
                        values: List[Any] = current.setdefault(key, [])
                        values.append(value)
                    else:
                        current[key] = value
                else:
                    current = current.setdefault(key, {})
        
        return data

    def _parse_key_path(self, key: str) -> List[str]:
        parts: List[str] = _nested_key_regex.findall(key)
        
        if parts:
            return [ p.strip("[]") if not p.endswith("[]") else p for p in parts ]
        
        return parts

def build_request_body(body: Any, content_type: Optional[str]) -> Any:
    if content_type == "application/json":
        return json.dumps(body)
    
    if content_type == "multipart/form-data":
        return build_request_form(body)

    if content_type == "application/x-www-form-urlencoded":
        return urlencode(body)

    if isinstance(body, (str, bytes)):
        return body

    return body

def build_request_form(body: Any) -> aiohttp.FormData:
    form = aiohttp.FormData()

    for key, value in body.items() if isinstance(body, dict) else {}:
        if isinstance(value, UploadFile):
            content_type, _ = parse_options_header(value.headers, "Content-Type")
            form.add_field(
                name=key,
                value=value.file,
                filename=value.filename,
                content_type=content_type or "application/octet-stream"
            )
        else:
            form.add_field(name=key, value=str(value))

    return form

async def parse_request_body(request: Request, content_type: str, nested: bool = False) -> Any:
    if content_type in [ "multipart/form-data", "application/x-www-form-urlencoded" ]:
        return await parse_request_form(request, nested)

    if content_type == "application/json":
        return await request.json()

    if content_type.startswith("text/"):
        return str(await request.body())

    return await request.body()

async def parse_request_form(request: Request, nested: bool = False) -> Any:
    form = await request.form()

    if nested:
        return NestedFormParser().parse(form)

    return form

def parse_options_header(headers: Dict[str, str], header_name: str) -> Tuple[str, Dict[str, str]]:
    value = CaseInsensitiveDict(headers or {}).get(header_name, "")
    pos = _firefox_escape_fix_regex.sub("%22", value).find(";")
    
    if pos >= 0:
        options = { 
            m.group(1).lower(): m.group(2) or m.group(3).replace("%22", "") for m in _option_regex.finditer(value[pos:])
        }
        value = value[:pos]
    else:
        options = {}

    return value.strip().lower(), options

def create_upload_file(path: str, type: Optional[str], subtype: Optional[str]) -> UploadFile:
    file, filename = open(path, "rb"), os.path.basename(path)
    content_type = guess_file_content_type(filename, type, subtype)
    headers = { 
        "Content-Type": content_type,
        "Content-Disposition": f'form-data; filename="{filename}"'
    }

    return UploadFile(file=file, filename=filename, headers=headers)

def guess_file_content_type(filename: str, type: Optional[str], subtype: Optional[str]) -> str:
    subtype = filename.split(".")[-1] if not subtype else subtype
    
    if type in [ "image", "audio", "video" ] and subtype:
        return f"{type}/{subtype}"

    return "application/octet-stream"
