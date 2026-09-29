from django.db import IntegrityError, transaction
from django.utils import timezone


def allocate_transaction_number(today=None):
    """RE-YYYYMM-NNNN を排他的に払い出す（月ごとの連番）。"""
    from .models import RealEstateNumberSequence

    today = today or timezone.localdate()
    key = f'RE-{today:%Y%m}'
    for _ in range(3):
        try:
            with transaction.atomic():
                seq, _ = RealEstateNumberSequence.objects.select_for_update().get_or_create(key=key)
                seq.last_number += 1
                seq.save(update_fields=['last_number'])
            return f'{key}-{seq.last_number:04d}'
        except IntegrityError:
            continue
    raise RuntimeError('番号を採番できませんでした。')
