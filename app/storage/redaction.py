"""
VisionPilot Privacy and Data Redaction Layer.

Ensures that sensitive information (passwords, tokens, API keys, credentials,
and personal identifiers) is automatically redacted before persistence to SQLite.
Provides local-first, zero-leak privacy protection in accordance with Rule 4 and Rule 28.
"""
import re
from typing import Any, Dict, List, Union


class PrivacyRedactor:
    """Robust, regex-based privacy redaction utility for task and audit history."""

    # Patterns matching sensitive token structures
    API_KEY_PATTERNS = [
        re.compile(r"(sk-[a-zA-Z0-9_\-]{20,})", re.IGNORECASE),                         # OpenAI / Anthropic
        re.compile(r"(AIza[0-9A-Za-z-_]{35})", re.IGNORECASE),                           # Google API keys
        re.compile(r"(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})", re.IGNORECASE), # GitHub tokens
        re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),                # Bearer tokens
        re.compile(r"([a-f0-9]{32,64})", re.IGNORECASE),                                # Hex keys / hashes > 32 chars
    ]

    # Sensitive key identifiers
    SENSITIVE_KEY_NAMES = {
        "password", "pwd", "pass", "secret", "token", "api_key", "apikey",
        "access_token", "auth", "authorization", "private_key", "credential",
        "credit_card", "cvv", "ssn"
    }

    # Sensitive targets or parameter keywords
    PASSWORD_FIELD_INDICATORS = {
        "password", "pin", "passcode", "secret", "token", "ssn", "cvv"
    }

    @classmethod
    def redact_text(cls, text: str = "") -> str:
        """Redacts sensitive strings, API keys, and credential-like substrings."""
        if not text:
            return ""

        redacted = text
        for pat in cls.API_KEY_PATTERNS:
            if pat.pattern.startswith("(Bearer"):
                redacted = pat.sub(r"\1<redacted:token>", redacted)
            else:
                redacted = pat.sub("<redacted:key>", redacted)

        return redacted

    @classmethod
    def redact_error(cls, error_msg: str) -> str:
        """Sanitizes error messages, stack fragments, and token references."""
        if not error_msg:
            return ""
        return cls.redact_text(error_msg)

    @classmethod
    def redact_dict(cls, data: Union[Dict[str, Any], List[Any], Any]) -> Any:
        """Recursively traverses and redacts dictionary entries and lists."""
        if isinstance(data, dict):
            cleaned: Dict[str, Any] = {}
            for k, v in data.items():
                k_lower = str(k).lower()
                # Check if key itself denotes a secret
                if any(sec in k_lower for sec in cls.SENSITIVE_KEY_NAMES):
                    cleaned[k] = "<redacted:credential>"
                elif k_lower in ("text", "value", "input") and isinstance(v, str):
                    # If nearby fields indicate password
                    target_name = str(data.get("target", "") or data.get("field", "")).lower()
                    if any(pw in target_name for pw in cls.PASSWORD_FIELD_INDICATORS):
                        cleaned[k] = "<redacted:password>"
                    else:
                        cleaned[k] = cls.redact_text(v)
                else:
                    cleaned[k] = cls.redact_dict(v)
            return cleaned

        elif isinstance(data, list):
            return [cls.redact_dict(item) for item in data]

        elif isinstance(data, str):
            return cls.redact_text(data)

        return data

    @classmethod
    def redact_action_parameters(cls, capability: str, target_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Specialized redaction for action execution parameters."""
        cleaned = cls.redact_dict(parameters)
        target_lower = str(target_name).lower()
        if capability in ("TYPE_TEXT", "SET_VALUE", "FILL_FORM"):
            if any(p in target_lower for p in cls.PASSWORD_FIELD_INDICATORS):
                if "text" in cleaned:
                    cleaned["text"] = "<redacted:password>"
                if "value" in cleaned:
                    cleaned["value"] = "<redacted:password>"

        return cleaned
