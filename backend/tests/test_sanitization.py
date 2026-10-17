from app.utils.sanitization import sanitize_text, normalize_identifier

def test_sanitize_text():
    # Removes extra whitespace
    assert sanitize_text("  hello   world  \n\n\n test ") == "hello world \n\n test"
    
    # Truncates correctly
    long_text = "A" * 6000
    sanitized = sanitize_text(long_text, max_length=5000)
    assert len(sanitized) == 5015  # 5000 + len("... [TRUNCATED]")
    assert sanitized.endswith("... [TRUNCATED]")
    
def test_normalize_identifier():
    assert normalize_identifier("john.doe@example.com") == "john.doe@example.com"
    assert normalize_identifier("Hello @ World!") == "Hello @ World"  # Removes !
    assert normalize_identifier(None) == "Anonymous"
    assert normalize_identifier("") == "Anonymous"
