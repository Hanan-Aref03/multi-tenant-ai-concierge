from services.guardrails.redaction import redact, redact_text


def test_redacts_email_addresses() -> None:
    result = redact_text("Contact admin@example.com for help.")

    assert result.text == "Contact [REDACTED_EMAIL] for help."
    assert result.redactions == ("email",)


def test_redacts_phone_number_like_values() -> None:
    result = redact_text("Call +1 (555) 123-4567 today.")

    assert result.text == "Call [REDACTED_PHONE] today."
    assert result.redactions == ("phone",)


def test_redacts_api_key_like_secrets() -> None:
    text = "Keys: sk-abc123456789 gsk_secret123456 xoxb-12345678-abcdef ghp_abcdef123456"

    result = redact_text(text)

    assert result.text == "Keys: [REDACTED_API_KEY] [REDACTED_API_KEY] [REDACTED_API_KEY] [REDACTED_API_KEY]"
    assert result.redactions == ("api_key",)


def test_redacts_bearer_and_authorization_tokens() -> None:
    text = "Authorization: Bearer abcdef123456789 and Bearer zyx987654321"

    result = redact_text(text)

    assert result.text == "[REDACTED_AUTH_TOKEN] and Bearer [REDACTED_BEARER_TOKEN]"
    assert result.redactions == ("authorization_token", "bearer_token")


def test_redact_returns_only_text() -> None:
    assert redact("hello test@example.com") == "hello [REDACTED_EMAIL]"
