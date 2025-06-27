from typing import Union, List, Type
from pydantic import BaseModel, ValidationError
from .schema.compose import ComposeConfig
from pathlib import Path
import yaml

def load_config_models(config_name: str, work_dir: Union[ str, Path ], config_files: List[Union[ str, Path ]], model_class: Type[BaseModel]) -> List[BaseModel]:
    if len(config_files) == 0:
        for ext in [ ".yml", ".yaml" ]:
            config_file = Path(work_dir) / f"{config_name}{ext}"
            if config_file.exists():
                config_files.append(config_file)
                break
        else:
            raise FileNotFoundError(f"{config_name}.yml or .yaml not found")
    
    config_dicts = []
    for config_file in config_files:
        with open(config_file, "r", encoding="utf-8") as f:
            try:
                config_dicts.append(yaml.safe_load(f))
            except yaml.YAMLError as e:
                raise ValueError(f"YAML parsing error:\n{e}")
    
    validated_configs = []
    for config_dict in config_dicts:
        try:
            validated_configs.append(model_class.model_validate(config_dict))
        except ValidationError as e:
            raise ValueError(f"Config validation failed:\n{e.json(indent=2)}")
        
    return validated_configs

def load_compose_config(work_dir: Union[ str, Path ], config_files: List[Union[ str, Path ]]) -> ComposeConfig:
    config_models = load_config_models("model-compose", work_dir, config_files, ComposeConfig)
    merged_config = config_models[0] # TODO

    return merged_config
