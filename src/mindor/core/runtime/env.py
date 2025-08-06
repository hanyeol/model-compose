from typing import Union, Dict, List
from pathlib import Path
from dotenv import dotenv_values

def load_env_files(work_dir: Union[ str, Path ], env_files: List[Union[ str, Path ]]) -> Dict[str, str]:
    if len(env_files) == 0:
        env_file = Path(work_dir) / ".env"
        if env_file.exists():
            env_files.append(env_file)
    
    env_dicts = []
    for env_file in env_files:
        env_dicts.append(dotenv_values(env_file))

    merged_env = {}
    for env_dict in env_dicts:
        merged_env.update({k: v for k, v in env_dict.items() if v is not None})

    return merged_env

def merge_env_data(env: Dict[str, str], env_data: List[str]) -> Dict[str, str]:
    for env_entry in env_data:
        if "=" not in env_entry:
            raise ValueError(f"Invalid env entry: {env_entry}")
        
        key, value = env_entry.split("=", 1)
        env[key] = value

    return env
