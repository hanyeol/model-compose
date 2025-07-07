from typing import Union, List

def is_status_code_matched(status_code: int, conditions: List[Union[int, str]]) -> bool:
    for condition in conditions:
        if isinstance(condition, int) or (isinstance(condition, str) and condition.isdigit()):
            if status_code == int(condition):
                return True
            continue

        if isinstance(condition, str) and condition.endswith("x"):
            try:
                prefix = int(condition.rstrip("x"))
                factor = 10 ** (len(condition) - len(str(prefix)))
                if prefix * factor <= status_code < (prefix + 1) * factor:
                    return True
            except ValueError:
                pass
            continue

    return False
