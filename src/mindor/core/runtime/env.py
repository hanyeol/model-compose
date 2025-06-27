from typing import Union, Dict, List
from pathlib import Path
from dotenv import dotenv_values

def load_env_files(work_dir: Union[ str, Path ], env_files: List[Union[ str, Path ]]) -> Dict[str, str]:
    if len(env_files) == 0:
        env_file = Path(work_dir) / ".env"
        if env_file.exists():
            env_files.append(env_file)
        else:
            raise FileNotFoundError(".env not found.")
    
    env_dicts = []
    for env_file in env_files:
        env_dicts.append(dotenv_values(env_file))

    merged_env = {}
    for env_dict in env_dicts:
        merged_env.update({k: v for k, v in env_dict.items() if v is not None})

    return merged_env
