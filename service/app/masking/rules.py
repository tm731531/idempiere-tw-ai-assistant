# service/app/masking/rules.py
"""PII column rules for Taiwan Personal Data Protection Act compliance."""

import re

# Maps PII column name patterns to token prefixes.
# Token format: [PII_PREFIX_NNN] — PII_ prefix avoids natural text collision.
PII_COLUMN_RULES: dict[str, str] = {
    "name": "C",        # Customer/contact name
    "taxid": "T",       # Tax ID / national ID
    "phone": "P",       # Phone number
    "email": "E",       # Email address
    "address": "A",     # Address
    "birthday": "D",    # Date of birth
}

# Regex to match PII tokens in text (for input sanitization)
PII_TOKEN_PATTERN = re.compile(r"\[PII_[A-Z]_\d{3}\]")
