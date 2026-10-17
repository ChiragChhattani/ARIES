"""
Input Sanitization Utilities.

Protects the application from maliciously large inputs or 
poorly formatted data copied from Word documents.
"""

import re

def sanitize_text(text: str, max_length: int = 5000) -> str:
    """
    Cleans string input and enforces a strict maximum length.
    
    Args:
        text: The raw input string.
        max_length: Maximum allowed characters.
        
    Returns:
        A cleaned, truncated string.
    """
    if not text:
        return ""
        
    # Strip leading/trailing whitespace
    cleaned = text.strip()
    
    # Replace multiple spaces/newlines with a single space/newline
    # (Helps clean up messy copy-pastes from PDFs/Word)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'[\r\n]{3,}', '\n\n', cleaned)
    
    # Truncate to max length to prevent prompt injection payload bloat
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "... [TRUNCATED]"
        
    return cleaned


def normalize_identifier(identifier: str) -> str:
    """Normalizes candidate identifiers to prevent weird characters."""
    if not identifier:
        return "Anonymous"
    # Allow alphanumeric, spaces, dashes, underscores, and emails
    cleaned = re.sub(r'[^a-zA-Z0-9 @._-]', '', identifier)
    return cleaned.strip()[:100]
