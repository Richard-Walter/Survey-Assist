from decimal import Decimal
import math

FIELD_TYPE_ANGLE = 'angle'
FIELD_TYPE_FLOAT = 'float'
FIELD_TYPE_NUMBER = 'number'


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

def angle_DMS_2_decimal(angle_deg, angle_min, angle_sec):
    # str_value = str(angle_deg) + '.' + '{:.3f}'.format(float(angle_min)/60) + '{:.3f}'.format(float(angle_sec)/3600)
    return float(angle_deg) + float(angle_min)/60 + float(angle_sec)/(60*60)

def angular_difference(angle_1, angle_2, angle):

    rad_a = deg2rad(angle_1)
    rad_b = deg2rad(angle_2)
    if angle == 180:
        rad_diff = max([rad_a, rad_b]) - min([rad_a, rad_b])
        angular_diff = abs(angle - rad2deg(rad_diff))
    else:
        rad_diff = rad_a + rad_b
        angular_diff = abs(angle - rad2deg(rad_diff))
    return round(angular_diff, 6)


def get_time_differance(time1, time2):
    time1_list = time1.split(':')
    time2_list = time2.split(':')

    hrs1 = int(time1_list[0])
    min1 = int(time1_list[1])

    hrs2 = int(time2_list[0])
    min2 = int(time2_list[1])

    time_diff_hr = '{:.2f}'.format(hrs2 - hrs1)
    time_diff_mins = '{:.2f}'.format(min2 - min1)

    return time_diff_hr + ':' + time_diff_mins


def get_numerical_value_from_string(str_value, field_type, precision='3dp'):
    if field_type == FIELD_TYPE_NUMBER:
        return int(str_value)
    elif field_type == FIELD_TYPE_ANGLE:
        # e.g '035° 13\' 27"'
        angle_list = str_value.split()
        angle_deg = angle_list[0].replace('°', '')
        angle_min = angle_list[1].replace('\'', '')
        angle_sec = angle_list[2].replace('\"', '')

        return angle_DMS_2_decimal(angle_deg, angle_min, angle_sec)

    elif field_type == FIELD_TYPE_FLOAT:
        return decimalize_value(float(str_value), precision) if str_value != "" else ""
