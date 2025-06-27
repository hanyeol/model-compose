from datetime import timedelta

def parse_duration(string: str) -> timedelta:
    if string.endswith("s"):
        return timedelta(seconds=int(string[:-1]))
    
    if string.endswith("m"):
            return timedelta(minutes=int(string[:-1]))
    
    if string.endswith("h"):
        return timedelta(hours=int(string[:-1]))
    
    raise ValueError(f"Unsupported duration format: {string}")
