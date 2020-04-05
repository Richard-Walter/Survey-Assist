from decimal import Decimal


def decimalize_value(in_value, precision):
    if precision == '4dp':
        return Decimal(in_value).quantize(Decimal('1.0000'))
    else:
        return Decimal(in_value).quantize(Decimal('1.000'))