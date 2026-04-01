# service/app/masking/masker.py
"""Reversible PII masking for database query results."""

from app.masking.rules import PII_COLUMN_RULES, PII_TOKEN_PATTERN


class PIIMasker:
    """Reversible PII masking for database query results."""

    def mask(
        self, rows: list[dict], pii_columns: list[str]
    ) -> tuple[list[dict], dict[str, str]]:
        """
        Replace PII values with tokens.
        
        Args:
            rows: List of database result rows (dicts)
            pii_columns: List of column names to mask
            
        Returns:
            Tuple of (masked_rows, token_to_original_mapping)
        """
        mapping: dict[str, str] = {}
        reverse: dict[str, str] = {}
        counters: dict[str, int] = {}

        masked_rows = []
        for row in rows:
            masked_row = dict(row)
            for col in pii_columns:
                val = row.get(col)
                if val is None:
                    continue
                str_val = str(val)

                if str_val in reverse:
                    masked_row[col] = reverse[str_val]
                else:
                    prefix = PII_COLUMN_RULES.get(col.lower(), "X")
                    counters.setdefault(prefix, 0)
                    counters[prefix] += 1
                    token = f"[PII_{prefix}_{counters[prefix]:03d}]"
                    mapping[token] = str_val
                    reverse[str_val] = token
                    masked_row[col] = token
            masked_rows.append(masked_row)

        return masked_rows, mapping

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        """
        Replace tokens in text back to original PII values.
        
        Args:
            text: Text containing PII tokens
            mapping: Token to original value mapping
            
        Returns:
            Text with PII restored
        """
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

    def sanitize_input(self, text: str) -> str:
        """
        Strip PII token patterns from user input to prevent prompt injection.
        
        Args:
            text: User's question
            
        Returns:
            Sanitized text with PII tokens removed
        """
        return PII_TOKEN_PATTERN.sub("", text).strip()
