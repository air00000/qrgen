# app/utils/helpers.py
"""
Shared utility helpers for the QR generation API.
Provides consistent handling of:
- Missing fields with defaults
- Data URI parsing for photos
- Text truncation with ellipsis
"""
import base64
import re
from typing import Optional


# ===== Field Length Constants =====
# Maximum lengths for text fields before truncation
MAX_LENGTH_TITLE = 25  # Название товара - максимум 25 символов
MAX_LENGTH_NAME = 50
MAX_LENGTH_ADDRESS = 100
MAX_LENGTH_URL = 500


def get_field_with_default(data: dict, field: str, default: any = "") -> any:
    """
    Get field from data dict with a default value if missing.
    
    Args:
        data: Dictionary containing request data
        field: Field name to retrieve
        default: Default value if field is missing (default: empty string)
    
    Returns:
        Field value or default if not present
    """
    return data.get(field, default) if data.get(field) is not None else default


def parse_data_uri(data_uri: Optional[str]) -> Optional[str]:
    """
    Parse Data URI format and extract base64 data.
    
    Accepts both formats:
    - Data URI: data:image/png;base64,iVBORw0...
    - Plain base64: iVBORw0... (for backward compatibility)
    
    Args:
        data_uri: Data URI string, plain base64, or None
    
    Returns:
        Base64 string without Data URI prefix, or None if:
        - Input is None/empty
        - Format is invalid/malformed
        - Cannot be parsed
    
    Note:
        This function does NOT raise errors for malformed input.
        Instead, it returns None, allowing generation to continue
        with an empty/missing photo.
    """
    if not data_uri:
        return None
    
    # If it's plain base64 (backward compatibility), return as-is
    if not data_uri.startswith('data:'):
        return data_uri
    
    try:
        # Match pattern: data:image/xxx;base64,<data>
        match = re.match(r'^data:image/[^;]+;base64,(.+)$', data_uri)
        if match:
            return match.group(1)
        
        # Try alternative format without image type: data:;base64,<data>
        match = re.match(r'^data:;base64,(.+)$', data_uri)
        if match:
            return match.group(1)
        
        # Malformed Data URI - return None, don't fail
        return None
        
    except Exception:
        # Any parsing error - return None, don't fail
        return None


def truncate_with_ellipsis(text: str, max_length: int) -> str:
    """
    Truncate text to max_length with ellipsis if needed.
    
    Truncation rule:
    - If text length <= max_length: return as-is
    - If text length > max_length: cut to (max_length - 3) and append "..."
      so total length equals max_length
    
    Args:
        text: Text to truncate
        max_length: Maximum allowed length (including ellipsis if added)
    
    Returns:
        Truncated text with "..." if it exceeded max_length
    
    Examples:
        >>> truncate_with_ellipsis("Hello", 10)
        'Hello'
        >>> truncate_with_ellipsis("This is a very long title", 15)
        'This is a ve...'
    """
    if not text:
        return text
    
    if len(text) <= max_length:
        return text
    
    # Cut to max_length - 3, then add "..."
    return text[:max_length - 3] + "..."


def truncate_title(title: str) -> str:
    """Truncate title field to MAX_LENGTH_TITLE"""
    return truncate_with_ellipsis(title, MAX_LENGTH_TITLE)


def truncate_name(name: str) -> str:
    """Truncate name field to MAX_LENGTH_NAME"""
    return truncate_with_ellipsis(name, MAX_LENGTH_NAME)


def truncate_address(address: str) -> str:
    """Truncate address field to MAX_LENGTH_ADDRESS"""
    return truncate_with_ellipsis(address, MAX_LENGTH_ADDRESS)


def truncate_url(url: str) -> str:
    """Truncate URL field to MAX_LENGTH_URL"""
    return truncate_with_ellipsis(url, MAX_LENGTH_URL)
