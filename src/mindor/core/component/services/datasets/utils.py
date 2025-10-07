from typing import Dict, List, Any
import re

def format_template_example(template: str, example: Dict[str, Any]) -> str:
    column_names = set(re.findall(r"\{(\w+)\}", template))
    formatted = template

    for column in column_names:
        if column in example:
            formatted = formatted.replace(f"{{{column}}}", str(example[column]))

    return formatted
