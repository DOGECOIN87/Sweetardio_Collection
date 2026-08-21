#!/usr/bin/env python3
"""Where the sun is, for a token's locale — with no API call.

Solar position is pure astronomy, so the time-of-day half of the dynamic
trait needs no network, no key and no rate limit: given a latitude, a
longitude and a UTC instant, the sun's altitude above the horizon is a
closed-form calculation. Only the WEATHER half needs an external service.

This is the NOAA solar position algorithm (the one behind the NOAA solar
calculator), accurate to well under a tenth of a degree for any date this
collection will live through — far finer than the phase bands in sky.py,
which are tens of degrees wide.

The altitude angle, not the clock, is what drives the art. "18:00" is a
different sky in Reykjavik and Singapore, and a different sky in June and
December; -6 degrees of solar altitude is blue hour everywhere, always.
That is the whole reason this file exists instead of a table of sunset
times.
"""

import datetime
import math

# ---------------------------------------------------------------- phases
#
# Boundaries are in degrees of solar altitude (refraction-corrected), and
# they are the standard astronomical definitions rather than numbers picked
# to look nice:
#
#   -18  astronomical twilight : the sky is fully dark below this
#   -12  nautical twilight     : horizon becomes distinguishable
#    -6  civil twilight        : "blue hour"; you can no longer read outside
#  -0.833 sunrise/sunset       : the disc touches the horizon (refraction)
#    +6  end of golden hour    : the warm light is gone
#
# Above +6 the collection simply looks like itself: DAY is the canonical
# grade the plates were approved at, and it is deliberately an identity
# pass. Most holders, most of the time, see the art exactly as minted.
SUNRISE_ALT = -0.833
GOLDEN_ALT = 6.0
CIVIL_ALT = -6.0
NAUTICAL_ALT = -12.0
HIGH_SUN_ALT = 50.0


def _julian_day(dt_utc):
    """Julian Day number for a timezone-aware UTC datetime."""
    y, m = dt_utc.year, dt_utc.month
    day = (dt_utc.day
           + (dt_utc.hour + dt_utc.minute / 60.0
              + dt_utc.second / 3600.0) / 24.0)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (int(365.25 * (y + 4716)) + int(30.6001 * (m + 1))
            + day + b - 1524.5)


def _refraction(alt_deg):
    """Atmospheric refraction, in degrees, lifting an apparent altitude.

    Matters precisely where this feature is most interesting: near the
    horizon the sun appears about half a degree higher than it is, which is
    why sunset is defined at -0.833 rather than 0.
    """
    if alt_deg > 85.0:
        return 0.0
    t = math.tan(math.radians(alt_deg))
    if alt_deg > 5.0:
        r = 58.1 / t - 0.07 / t ** 3 + 0.000086 / t ** 5
    elif alt_deg > -0.575:
        r = (1735.0 + alt_deg * (-518.2 + alt_deg
             * (103.4 + alt_deg * (-12.79 + alt_deg * 0.711))))
    else:
        r = -20.772 / t
    return r / 3600.0


def solar_position(lat, lon, when_utc):
    """Apparent (altitude, azimuth) of the sun in degrees.

    lat/lon in signed decimal degrees (north and east positive).
    when_utc must be a timezone-aware UTC datetime.
    """
    jd = _julian_day(when_utc)
    t = (jd - 2451545.0) / 36525.0

    # Geometric mean longitude and anomaly of the sun
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)

    # Equation of centre -> true, then apparent longitude
    centre = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
              + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
              + math.sin(3 * mr) * 0.000289)
    true_long = l0 + centre
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    # Obliquity of the ecliptic, corrected
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059
                   - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    decl = math.degrees(math.asin(math.sin(math.radians(eps))
                                  * math.sin(math.radians(app_long))))

    # Equation of time (minutes) -> true solar time -> hour angle
    yv = math.tan(math.radians(eps / 2.0)) ** 2
    l0r = math.radians(l0)
    eot = 4.0 * math.degrees(
        yv * math.sin(2 * l0r)
        - 2.0 * ecc * math.sin(mr)
        + 4.0 * ecc * yv * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * yv * yv * math.sin(4 * l0r)
        - 1.25 * ecc * ecc * math.sin(2 * mr))

    minutes = (when_utc.hour * 60.0 + when_utc.minute
               + when_utc.second / 60.0)
    true_solar = (minutes + eot + 4.0 * lon) % 1440.0
    hour_angle = true_solar / 4.0 - 180.0

    latr, declr = math.radians(lat), math.radians(decl)
    har = math.radians(hour_angle)
    cos_zen = (math.sin(latr) * math.sin(declr)
               + math.cos(latr) * math.cos(declr) * math.cos(har))
    cos_zen = max(-1.0, min(1.0, cos_zen))
    zenith = math.degrees(math.acos(cos_zen))
    alt = 90.0 - zenith + _refraction(90.0 - zenith)

    # Azimuth, clockwise from north
    sin_zen = math.sin(math.radians(zenith))
    if abs(sin_zen) < 1e-9:
        azi = 0.0
    else:
        ca = ((math.sin(latr) * math.cos(math.radians(zenith))
               - math.sin(declr)) / (math.cos(latr) * sin_zen))
        ca = max(-1.0, min(1.0, ca))
        azi = 180.0 - math.degrees(math.acos(ca))
        if hour_angle > 0:
            azi = 360.0 - azi
        azi %= 360.0
    return alt, azi


def is_rising(lat, lon, when_utc):
    """True if the sun is climbing — i.e. we are on the dawn side of the day.

    Sunrise and sunset sit at the SAME solar altitude, so altitude alone
    cannot tell a token in Tokyo at 05:40 from one at 18:20. It is the
    difference between a rose dawn and an amber dusk, which is the most
    visible split in the whole phase table, so it gets its own test: sample
    the altitude fifteen minutes later and see which way it went.
    """
    a0, _ = solar_position(lat, lon, when_utc)
    a1, _ = solar_position(lat, lon,
                           when_utc + datetime.timedelta(minutes=15))
    return a1 > a0


def sun_phase(lat, lon, when_utc):
    """Classify the sky into one of the eight named phases in sky.py.

    Returns (phase_name, altitude_degrees).
    """
    alt, _ = solar_position(lat, lon, when_utc)
    if alt >= HIGH_SUN_ALT:
        return "high_noon", alt
    if alt >= GOLDEN_ALT:
        return "day", alt
    rising = is_rising(lat, lon, when_utc)
    if alt >= SUNRISE_ALT:
        return ("golden_dawn" if rising else "golden_dusk"), alt
    if alt >= CIVIL_ALT:
        return ("blue_dawn" if rising else "blue_dusk"), alt
    if alt >= NAUTICAL_ALT:
        return "twilight", alt
    return "night", alt


def phase_progress(alt):
    """0..1 position of the altitude inside its own phase band.

    Lets a renderer interpolate between two neighbouring phase grades
    instead of snapping, so a token does not visibly jump at a boundary.
    The cached-render service quantises this (see render.py) — it exists so
    a live client-side view can be continuous.
    """
    bands = [(-90.0, NAUTICAL_ALT), (NAUTICAL_ALT, CIVIL_ALT),
             (CIVIL_ALT, SUNRISE_ALT), (SUNRISE_ALT, GOLDEN_ALT),
             (GOLDEN_ALT, HIGH_SUN_ALT), (HIGH_SUN_ALT, 90.0)]
    for lo, hi in bands:
        if lo <= alt < hi:
            return (alt - lo) / (hi - lo)
    return 1.0


if __name__ == "__main__":
    # Sanity check: the same instant is a different sky in each city.
    now = datetime.datetime(2026, 8, 21, 18, 0, tzinfo=datetime.timezone.utc)
    cities = [("Reykjavik", 64.15, -21.94), ("London", 51.51, -0.13),
              ("New York", 40.71, -74.01), ("Singapore", 1.35, 103.82),
              ("Tokyo", 35.68, 139.65), ("Sydney", -33.87, 151.21)]
    print(f"{now:%Y-%m-%d %H:%M} UTC")
    for name, la, lo in cities:
        ph, alt = sun_phase(la, lo, now)
        print(f"  {name:<10} alt {alt:+7.2f}  {ph}")
