from typing import Union, Dict, List, Type, Any
from pydantic import BaseModel, ValidationError
from .schema.compose import ComposeConfig
from pathlib import Path
from copy import deepcopy
import yaml, re

class ComposeConfigLoader:
    def __init__(self, config_name: str):
        self.config_name: str = config_name
        self.patterns = {
            "environment": re.compile(
                r"""\$\{                   # ${
                    (?:\s*env\.([^\s|}]+)) # name
                    (?:\s*\|\s*([^\s}]+))? # default value after `|`
                \s*\}""",                  # }
                re.VERBOSE,
            )
        }

    def load(self, work_dir: Union[ str, Path ], config_files: List[Union[ str, Path ]], env: Dict[str, str]) -> ComposeConfig:
        if len(config_files) == 0:
            for ext in [ ".yml", ".yaml" ]:
                config_file = Path(work_dir) / f"{self.config_name}{ext}"
                if config_file.exists():
                    config_files.append(config_file)
                    break
            else:
                raise FileNotFoundError(f"{self.config_name}.yml or .yaml not found")
        
        config_dicts = []
        for config_file in config_files:
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    text = self._resolve_environment_variables(f.read(), env)
                    try:
                        config_dicts.append(yaml.safe_load(text))
                    except yaml.YAMLError as e:
                        raise ValueError(f"YAML parsing error:\n{e}")
            except FileNotFoundError:
                raise FileNotFoundError(f"Config file not found: {config_file}")

        merged_config_dict = config_dicts[0]
        for config_dict in config_dicts[1:]:
            merged_config_dict = self._merge_config_dict(merged_config_dict, config_dict)

        try:
            return ComposeConfig.model_validate(merged_config_dict)
        except ValidationError as e:
            raise ValueError(f"Config validation failed:\n{e.json(indent=2)}")

    def _resolve_environment_variables(self, text: str, env: Dict[str, str]) -> str:
        matches = list(self.patterns["environment"].finditer(text))

        for m in reversed(matches):
            name, default = m.group(1, 2)
            start, end = m.span()
            text = text[:start] + env.get(name, default) + text[end:]

        return text

    def _merge_config_dict(self, base_dict: Dict[str, Any], override_dict: Dict[str, Any]) -> dict:
        merged_dict = deepcopy(base_dict)

        for key, override_value in override_dict.items():
            if key in merged_dict:
                base_value = merged_dict[key]
                if isinstance(base_value, dict) and isinstance(override_value, dict):
                    merged_dict[key] = self._merge_config_dict(base_value, override_value)
                else:
                    merged_dict[key] = deepcopy(override_value)
            else:
                merged_dict[key] = deepcopy(override_value)

        return merged_dict

def load_compose_config(work_dir: Union[ str, Path ], config_files: List[Union[ str, Path ]], env: Dict[str, str]) -> ComposeConfig:
    return ComposeConfigLoader("model-compose").load(work_dir, config_files, env)
