#!/usr/bin/env python3
"""Open-Meteo's WMO codes, collapsed to the seven states sky.py grades.

sky.py's weather table has said "collapsed from Open-Meteo's ~100 WMO codes
by weather.py" since it was written; this is that file. It is the only part
of the dynamic trait that touches the network -- solar.py is closed-form
astronomy, so time of day needs no API, no key and no rate limit.

A CLEAR SKY IS None, NOT A STATE. The minted token already is the clear-sky
render, so there is nothing for a `clear` state to draw; every function
here returns None for it and sky.py takes None everywhere a state name
goes. A service seeing None should serve the ORIGINAL MINTED BYTES rather
than re-encode a copy of them.

Open-Meteo is the service because it is free for this scale, needs no key,
and takes a lat/lon directly rather than a place id, which matters when the
input is a claimed locale rather than a city from a list.

    from dynamic import weather
    state = weather.fetch(51.51, -0.13)          # -> 'rain', or None
    state = weather.classify(75, wind_kmh=48)    # -> 'blizzard'

WHAT COLLAPSES AND WHAT DOES NOT

The ~100 codes carry distinctions the art cannot show: drizzle and light
rain are the same trait no matter how different the code is, and a holder
cannot see the difference between "slight" and "moderate" rain falling
behind a Twinkie. So the four ordinary states, plus None, take the whole
table between them.

None takes MORE than the clear codes: cloud cover (2, 3) maps there too,
because `overcast` was retired and the honest mapping for a sky the art
has nothing to draw for is the same as for a sky with nothing in it.

The two severe states are gated on more than a code, and for opposite
reasons:

  blizzard  is not a WMO code. It is snow AND wind, and Open-Meteo returns
            the wind separately -- so it is derived here, from two fields,
            at the thresholds below.

  tornado   is not derivable from Open-Meteo AT ALL. There is no WMO code
  flooded   for either, and no field that implies one. Code 99 is a
            thunderstorm with heavy hail, which is the closest the table
            gets to a tornado and is still not one; and flooding is a
            consequence of rain over hours, terrain and drainage, not a
            reading of the sky at an instant -- the same 20mm of rain
            floods one valley and not the next. classify() therefore
            NEVER returns either. Both come from a severe-weather ALERT
            feed -- see from_alert() -- or are set by hand. Reading hail
            as a tornado would put the rarest state in the set on several
            thousand hailstorms a year; reading heavy rain as a flood
            would put a flood on most of the tropics most of the summer.

CALLING IT AT COLLECTION SCALE

4,444 tokens is a few hundred real cities, not 4,444 locations, so the
calls collapse hard: bucket the locale to ~25km, cache for 30 minutes, and
a full collection refresh is a few hundred requests an hour at worst.
Anything that renders a token calls fetch(), which is why the cache lives
here rather than in the caller.

A render must never fail because a weather API is slow or down. fetch()
returns FALLBACK on any error rather than raising, and a caller that wants
a token to keep its own sky across an outage should pass its token id --
see the fallback= argument and stable_state().
"""

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request

# ------------------------------------------------------------ the table
#
# Every code Open-Meteo documents, mapped to one of the four ordinary
# states or to None. Written out in full rather than as ranges: the table
# is the specification, and a range hides which codes exist. Anything not
# listed falls back to FALLBACK, which is also what an unreachable API
# returns.
WMO_STATES = {
    0: None,            # clear sky        -> no weather layer at all
    1: None,            # mainly clear     -> no weather layer at all
    # Cloud cover has no state to draw since `overcast` was retired, and
    # the honest mapping for "we have nothing to show for this" is the same
    # one a clear sky gets: no weather layer, serve the mint. Routing them
    # to fog or rain instead would be inventing weather the sky does not
    # have, on roughly a third of the planet at any moment.
    2: None,            # partly cloudy    -> no weather layer at all
    3: None,            # overcast         -> no weather layer at all

    45: "fog",          # fog
    48: "fog",          # depositing rime fog

    51: "rain",         # drizzle, light
    53: "rain",         # drizzle, moderate
    55: "rain",         # drizzle, dense
    56: "rain",         # freezing drizzle, light
    57: "rain",         # freezing drizzle, dense
    61: "rain",         # rain, slight
    63: "rain",         # rain, moderate
    65: "rain",         # rain, heavy
    66: "rain",         # freezing rain, light
    67: "rain",         # freezing rain, heavy
    80: "rain",         # rain showers, slight
    81: "rain",         # rain showers, moderate

    71: "snow",         # snow fall, slight
    73: "snow",         # snow fall, moderate
    75: "snow",         # snow fall, heavy
    77: "snow",         # snow grains
    85: "snow",         # snow showers, slight
    86: "snow",         # snow showers, heavy

    82: "storm",        # rain showers, violent
    95: "storm",        # thunderstorm, slight or moderate
    96: "storm",        # thunderstorm with slight hail
    99: "storm",        # thunderstorm with heavy hail
}

# What an unreachable API, an unknown code or a failed call returns: no
# weather. It has to be the state that costs the plate nothing, because it
# is the one served when the service knows nothing.
FALLBACK = None

# Snow codes heavy enough that ordinary wind turns them into a whiteout,
# versus the rest, which need a wind that would blow lying snow around by
# itself. Two rungs rather than one because a ground blizzard is real: 71
# is "slight snow", and at 60km/h you still cannot see.
HEAVY_SNOW = frozenset({73, 75, 86})
BLIZZARD_WIND_KMH = 35.0        # with heavy snow falling
BLIZZARD_GALE_KMH = 55.0        # with any snow at all

# The National Weather Service definition is 35 mph (56km/h) sustained,
# with falling or blowing snow reducing visibility below 400m, for three
# hours or more. That is a handful of tokens a year, worldwide -- rare
# enough to be a state nobody ever sees. The thresholds above are
# deliberately looser: BLIZZARD_GALE_KMH keeps the NWS wind for light
# snow, and BLIZZARD_WIND_KMH admits heavy snow at a gale that would
# whiteout in practice. Rare enough to be an event, common enough to exist.


def classify(code, wind_kmh=0.0):
    """One WMO code (+ wind) -> an ordinary state, a blizzard, or None.

    None is a clear sky: no weather layer, serve the mint unchanged.
    NEVER returns 'tornado'; there is no WMO code for one. See from_alert().
    """
    state = WMO_STATES.get(int(code), FALLBACK)
    if state == "snow":
        heavy = int(code) in HEAVY_SNOW
        if wind_kmh >= (BLIZZARD_WIND_KMH if heavy else BLIZZARD_GALE_KMH):
            return "blizzard"
    return state


# ------------------------------------------------------------ the alert
#
# Tornado is an EVENT state and has to arrive from an event feed. In the US
# that is the National Weather Service's active-alerts API
# (api.weather.gov/alerts/active, free, no key, GeoJSON); elsewhere it is
# whatever the national meteorological service publishes, and in much of
# the world it is nothing at all.
#
# Deliberately kept as a pure string test rather than a second HTTP client.
# Alert feeds differ per country in everything except that they name the
# hazard in a human-readable field, so the caller fetches its own feed and
# hands the event names here. That also makes the state settable by hand
# for a collection-wide event, which is the other reason to want it.
# Ordered MOST SEVERE FIRST, and the order is the whole point: a tornado
# warning and a flood warning are routinely active over the same county at
# the same time, and a token can only be in one state. The tornado wins
# because it is the rarer and the more specific of the two.
#
# "flash flood" is matched by "flood" already; it is not listed twice.
ALERT_STATES = (
    (("tornado", "waterspout"), "tornado"),
    (("flood", "storm surge", "levee"), "flooded"),
)


def from_alert(events, base="storm"):
    """Upgrade a state when an alert feed names a hazard the art can show.

    events : an iterable of alert names/headlines, or a single string.
    base   : the state to keep when no alert matches.

    These are the states no weather code can produce, so this is the only
    way either of them is ever returned. A warning is normally accompanied
    by the weather that caused it, so `base` is what classify() just
    returned and the alert REPLACES it rather than compounding it -- a
    token is in one state at a time.
    """
    if isinstance(events, str):
        events = [events]
    text = [str(e).lower() for e in (events or ())]
    for words, state in ALERT_STATES:
        if any(word in low for low in text for word in words):
            return state
    return base


# ----------------------------------------------------------- the caching
#
# Bucketed to a fixed 0.25-degree grid, which is ~27.8km at the equator and
# SHORTER toward the poles, because a degree of longitude shrinks with
# cos(latitude).
#
# That asymmetry is the right way round and the obvious "fix" is not:
# dividing the longitude bucket by cos(latitude) would widen the cells
# toward the poles and merge places hundreds of km apart at high latitude,
# where a good part of this collection's interesting weather is. A fixed
# grid over-splits there instead, which costs a few extra requests and
# never merges two locales more than ~28km apart.
BUCKET_DEG = 0.25
CACHE_TTL = 30 * 60             # seconds; weather does not move faster
API = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 6.0

_CACHE = {}                     # bucket -> (expires_at, state)


def bucket(lat, lon):
    """The cache key for a locale: a fixed ~25km grid cell."""
    return (math.floor(float(lat) / BUCKET_DEG),
            math.floor(float(lon) / BUCKET_DEG))


def _request(lat, lon):
    """Raw current-conditions call. Raises on any failure."""
    q = urllib.parse.urlencode({
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": "weather_code,wind_speed_10m",
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
    })
    with urllib.request.urlopen(f"{API}?{q}", timeout=TIMEOUT) as r:
        cur = json.load(r)["current"]
    return int(cur["weather_code"]), float(cur.get("wind_speed_10m", 0.0))


def fetch(lat, lon, now=None, fallback=FALLBACK, alerts=None):
    """The state for a locale, cached per ~25km bucket for 30 minutes.

    Never raises. A render request is on the critical path of somebody
    looking at their token, so a slow or broken weather service must cost
    them the dynamic layer and not the image -- `fallback` is returned
    instead, and nothing is cached, so the next call retries.

    alerts : optional iterable of alert names for this locale, passed
             straight to from_alert(); this is the only way 'tornado' is
             ever returned.
    """
    now = time.time() if now is None else now
    key = bucket(lat, lon)
    hit = _CACHE.get(key)
    if hit is not None and hit[0] > now:
        return from_alert(alerts, hit[1]) if alerts else hit[1]
    try:
        state = classify(*_request(float(lat), float(lon)))
    except Exception:
        return from_alert(alerts, fallback) if alerts else fallback
    _CACHE[key] = (now + CACHE_TTL, state)
    return from_alert(alerts, state) if alerts else state


def stable_state(token_id, weights=None):
    """A deterministic state for a token, for when there is no locale.

    The README's rule for locale applies to weather too: an unclaimed token
    should derive a stable pseudo-state from its id rather than defaulting
    everything to one value, so the collection always has tokens in every
    weather instead of 4,444 clear skies whenever the API is unreachable.

    Stable per token, so a holder's sky does not flicker between refreshes
    while the service is down.
    """
    w = dict(weights or DEFAULT_MIX)
    total = sum(w.values())
    # A 64-bit hash of the id, not python's hash() -- that one is salted
    # per process, so the same token would get a different sky on every
    # restart, which is the one thing this function exists to prevent.
    h = (int(token_id) * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
    x = (h >> 11) / float(2 ** 53) * total
    for state, weight in w.items():
        x -= weight
        if x <= 0:
            return state
    return FALLBACK


# Roughly how often each state should turn up when there is no real
# weather to read. Weighted to look like a year on earth rather than
# uniformly: most of the time it is clear or cloudy, and the two severe
# states stay rare enough to be worth seeing.
DEFAULT_MIX = {
    # None absorbs overcast's share: clear and cloudy are the same render
    # now, and between them they are most of the weather on earth.
    None: 63, "rain": 16, "fog": 7,
    "snow": 8, "storm": 4, "blizzard": 1, "tornado": 1, "flooded": 1,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--table", action="store_true",
                    help="print the WMO code table and the blizzard gate")
    args = ap.parse_args()

    if args.table or (args.lat is None or args.lon is None):
        by_state = {}
        for code, state in sorted(WMO_STATES.items()):
            by_state.setdefault(state, []).append(code)
        print(f"{len(WMO_STATES)} WMO codes -> "
              f"{len(by_state) - 1} states plus None\n")
        for state, codes in by_state.items():
            label = "None" if state is None else state
            print(f"  {label:9} {', '.join(str(c) for c in codes)}"
                  + ("   (no weather layer — serve the mint unchanged)"
                     if state is None else ""))
        print(f"\n  blizzard  snow + wind >= {BLIZZARD_WIND_KMH:.0f} km/h "
              f"(codes {sorted(HEAVY_SNOW)}) "
              f"or >= {BLIZZARD_GALE_KMH:.0f} km/h (any snow)")
        for words, state in ALERT_STATES:
            print(f"  {state:9} NOT derivable from a WMO code — needs an "
                  f"alert feed matching {list(words)}")
        print("\nstable_state() for tokens 1-12 (the no-locale fallback):")
        print("  " + "  ".join(f"{i}:{stable_state(i) or 'clear'}"
                               for i in range(1, 13)))

    if args.lat is not None and args.lon is not None:
        print(f"\nlive: {args.lat:.3f},{args.lon:.3f} "
              f"bucket {bucket(args.lat, args.lon)}")
        try:
            code, wind = _request(args.lat, args.lon)
            print(f"  WMO {code}, wind {wind:.0f} km/h "
                  f"-> {classify(code, wind)}")
        except Exception as exc:
            print(f"  unreachable ({type(exc).__name__}) -> "
                  f"fetch() returns {fetch(args.lat, args.lon)!r}")
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
