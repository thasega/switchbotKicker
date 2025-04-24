import math

def deg2rad(deg):
    return deg * math.pi / 180

def rad2deg(rad):
    return rad * 180 / math.pi

def calculate(day_of_year, leapyear, latitude, longitude, timezone_offset):
    gamma = (2 * math.pi / (366 if leapyear else 365)) * (day_of_year - 0.5) # 12:00:00

    eqtime = 229.18 * (
        0.000075 +
        0.001868 * math.cos(gamma) -
        0.032077 * math.sin(gamma) -
        0.014615 * math.cos(2 * gamma) -
        0.040849 * math.sin(2 * gamma)
    )

    decl = (
        0.006918 -
        0.399912 * math.cos(gamma) +
        0.070257 * math.sin(gamma) -
        0.006758 * math.cos(2 * gamma) +
        0.000907 * math.sin(2 * gamma) -
        0.002697 * math.cos(3 * gamma) +
        0.001480 * math.sin(3 * gamma)
    )

    lat_rad = deg2rad(latitude)
    zenith_angle = deg2rad(90.833)
    ha_sunrise_cos = (math.cos(zenith_angle) - math.sin(lat_rad) * math.sin(decl)) / (math.cos(lat_rad) * math.cos(decl))
    ha_sunrise = rad2deg(math.acos(min(1, max(-1, ha_sunrise_cos))))

    sunrise = 720 - 4 * (longitude + ha_sunrise) - eqtime
    sunset = 720 - 4 * (longitude - ha_sunrise) - eqtime
    solar_noon = 720 - 4 * longitude - eqtime

    moffset = timezone_offset * 60

    return {
        'noon': solar_noon + moffset,
        'sunrise': sunrise + moffset,
        'sunset': sunset + moffset,
    }


def convert_dayminute_to_timestring(minutes):
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    secs = int((minutes - hours * 60 - mins) * 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"

def convert_localtime_to_datestring(dt):
    return f"{dt[0]}/{dt[1]:02d}/{dt[2]:02d}"

def is_leapyear(y):
    if (y % 400 == 0): return True
    if (y % 100 == 0): return False
    if (y % 4 == 0): return True
    return False

