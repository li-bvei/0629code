from django.db import models

from .crypto import decrypt_text, encrypt_text


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts values at rest with Fernet.

    Equality lookups (filter/exclude on this field) will NOT match existing
    rows, since Fernet ciphertext is non-deterministic (same plaintext
    encrypts differently each time). Do not use this field in search_fields
    or filter() calls that expect exact-match lookups against stored data.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_text(value)

    def from_db_value(self, value, expression, connection):
        return decrypt_text(value)
