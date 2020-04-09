from decimal import Decimal
import math


def decimalize_value(in_value, precision):
    if precision == '4dp':
        return Decimal(in_value).quantize(Decimal('1.0000'))
    else:
        return Decimal(in_value).quantize(Decimal('1.000'))

def rad2deg(radians):
    degrees = 180 * radians / math.pi
    return degrees


def deg2rad(degrees):
    radians = math.pi * degrees / 180
    return radians


def angle_decimal2DMS(in_deg):
    min, sec = divmod(in_deg * 3600, 60)
    deg, min = divmod(min, 60)

    return str(int(deg)) + str(int(min)) + str(int(sec)) + ('0')


def angular_difference(angle_1, angle_2, angle):
    radA = deg2rad(angle_1)
    radB = deg2rad(angle_2)
    if angle == 180:
        radDiff = max([radA, radB]) - min([radA, radB])
        angular_diff = abs(angle - rad2deg(radDiff))
    else:
        radDiff = radA + radB
        angular_diff = abs(angle - rad2deg(radDiff))
    return round(angular_diff, 6)
