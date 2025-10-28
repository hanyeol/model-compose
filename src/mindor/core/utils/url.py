from urllib.parse import quote, urlparse, urlunparse

def encode_url(url_or_path: str) -> str:
    """
    Encode URL or path to handle special characters.

    For full URLs (with scheme and netloc):
        - Preserves scheme, host, and standard URL characters
        - Encodes special characters in the path part only (e.g., colons)

    For relative paths:
        - Encodes special characters including colons
        - Preserves slashes and standard path characters

    Args:
        url_or_path: Full URL or relative path

    Returns:
        Encoded URL or path

    Examples:
        >>> encode_url("https://api.example.com/images:annotate")
        'https://api.example.com/images%3Aannotate'

        >>> encode_url("images:annotate")
        'images%3Aannotate'
    """
    parsed = urlparse(url_or_path)

    if parsed.scheme and parsed.netloc:
        return url_or_path.replace(parsed.path, quote(parsed.path, safe="/"))
    
    return quote(url_or_path, safe="/")
