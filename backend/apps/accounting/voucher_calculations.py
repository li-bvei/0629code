from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


TAX_CATEGORY_10 = 'tax_10'
TAX_CATEGORY_8 = 'tax_8'
TAX_CATEGORY_NON_TAXABLE = 'non_taxable'
DEFAULT_TAX_CATEGORY = TAX_CATEGORY_10

PRICE_TYPE_TAX_INCLUDED = 'tax_included'
PRICE_TYPE_TAX_EXCLUDED = 'tax_excluded'
DEFAULT_PRICE_TYPE = PRICE_TYPE_TAX_INCLUDED
PRICE_TYPES = {PRICE_TYPE_TAX_INCLUDED, PRICE_TYPE_TAX_EXCLUDED}

TAX_CATEGORY_LABELS = {
    TAX_CATEGORY_10: '10％',
    TAX_CATEGORY_8: '8％',
    TAX_CATEGORY_NON_TAXABLE: '非課税',
}

TAX_RATES = {
    TAX_CATEGORY_10: Decimal('0.10'),
    TAX_CATEGORY_8: Decimal('0.08'),
    TAX_CATEGORY_NON_TAXABLE: Decimal('0'),
}

TAX_DIVISORS = {
    TAX_CATEGORY_10: Decimal('1.10'),
    TAX_CATEGORY_8: Decimal('1.08'),
}


class VoucherCalculationError(ValueError):
    pass


def decimal_to_number(value):
    if value is None:
        return 0
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def to_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise VoucherCalculationError('数量と単価は数字で入力してください。')


def normalize_tax_category(value):
    tax_category = str(value or DEFAULT_TAX_CATEGORY).strip()
    if tax_category not in TAX_RATES:
        raise VoucherCalculationError('税区分は 10％、8％、非課税 から選択してください。')
    return tax_category


def normalize_price_type(value):
    price_type = str(value or DEFAULT_PRICE_TYPE).strip()
    if price_type not in PRICE_TYPES:
        raise VoucherCalculationError('金額の税区分は税込・税抜から選択してください。')
    return price_type


def line_tax_parts(line_total, tax_category):
    if tax_category == TAX_CATEGORY_NON_TAXABLE:
        return line_total, Decimal('0')
    tax_excluded = (line_total / TAX_DIVISORS[tax_category]).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return tax_excluded, line_total - tax_excluded


def line_amounts_from_raw(raw_amount, tax_category, price_type):
    """quantity×単価 の生の金額から、税区分・税込/税抜の入力方式に応じて
    (税込金額, 税抜金額, 消費税額) を算出する。"""
    if tax_category == TAX_CATEGORY_NON_TAXABLE:
        return raw_amount, raw_amount, Decimal('0')
    if price_type == PRICE_TYPE_TAX_EXCLUDED:
        tax_excluded = raw_amount
        tax_amount = (tax_excluded * TAX_RATES[tax_category]).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return tax_excluded + tax_amount, tax_excluded, tax_amount
    tax_excluded, tax_amount = line_tax_parts(raw_amount, tax_category)
    return raw_amount, tax_excluded, tax_amount


def calculate_voucher_amounts(line_items):
    normalized_items = []
    summary = {
        'subtotal_10': Decimal('0'),
        'tax_10': Decimal('0'),
        'subtotal_8': Decimal('0'),
        'tax_8': Decimal('0'),
        'subtotal_non_taxable': Decimal('0'),
        'subtotal': Decimal('0'),
        'tax_total': Decimal('0'),
        'total': Decimal('0'),
    }

    if not isinstance(line_items, list):
        line_items = []

    for item in line_items:
        if not isinstance(item, dict):
            continue

        item_name = str(item.get('item_name') or '').strip()
        quantity = to_decimal(item.get('quantity'))
        unit_price = to_decimal(item.get('unit_price'))
        tax_category = normalize_tax_category(item.get('tax_category'))
        price_type = normalize_price_type(item.get('price_type'))

        if not item_name and quantity == 0 and unit_price == 0:
            continue

        raw_amount = (quantity * unit_price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        line_total, tax_excluded, tax_amount = line_amounts_from_raw(raw_amount, tax_category, price_type)

        if tax_category == TAX_CATEGORY_10:
            summary['subtotal_10'] += tax_excluded
            summary['tax_10'] += tax_amount
        elif tax_category == TAX_CATEGORY_8:
            summary['subtotal_8'] += tax_excluded
            summary['tax_8'] += tax_amount
        else:
            summary['subtotal_non_taxable'] += tax_excluded

        summary['subtotal'] += tax_excluded
        summary['tax_total'] += tax_amount
        summary['total'] += line_total

        normalized_items.append({
            **item,
            'item_name': item_name,
            'quantity': decimal_to_number(quantity),
            'unit_price': decimal_to_number(unit_price.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
            'line_total': int(line_total),
            'tax_category': tax_category,
            'tax_category_label': TAX_CATEGORY_LABELS[tax_category],
            'price_type': price_type if tax_category != TAX_CATEGORY_NON_TAXABLE else PRICE_TYPE_TAX_INCLUDED,
            'tax_excluded_amount': int(tax_excluded),
            'tax_amount': int(tax_amount),
        })

    return normalized_items, summary


def voucher_tax_summary(voucher):
    line_items, summary = calculate_voucher_amounts(voucher.line_items or [])
    if line_items:
        return summary

    total = to_decimal(getattr(voucher, 'total_amount', 0))
    subtotal = to_decimal(getattr(voucher, 'amount', 0))
    tax_total = to_decimal(getattr(voucher, 'tax_amount', 0))
    return {
        'subtotal_10': subtotal,
        'tax_10': tax_total,
        'subtotal_8': Decimal('0'),
        'tax_8': Decimal('0'),
        'subtotal_non_taxable': Decimal('0'),
        'subtotal': subtotal,
        'tax_total': tax_total,
        'total': total,
    }
