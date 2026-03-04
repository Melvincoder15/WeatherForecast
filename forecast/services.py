import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

BASE_URL = "https://api.openweathermap.org/data/2.5"
GEO_BASE_URL = "https://api.openweathermap.org/geo/1.0"


class WeatherServiceError(Exception):
    """Raised when weather data cannot be fetched or parsed."""

    def __init__(self, user_message: str, internal_message: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.internal_message = internal_message or user_message


def _build_location_params(query: str | None = None, lat: str | None = None, lon: str | None = None) -> dict:
    if lat and lon:
        return {"lat": lat, "lon": lon}

    value = (query or "").strip()
    if not value:
        raise WeatherServiceError("Please enter a city name or ZIP code to get started.")

    # Accept postal formats like 10001 or 10001,us as ZIP queries.
    if re.fullmatch(r"\d{4,10}(,[a-zA-Z]{2})?", value):
        return {"zip": value}

    return {"q": value}


def _get_api_key() -> str:
    api_key = settings.WEATHER_API_KEY
    if not api_key:
        raise WeatherServiceError(
            "WEATHER_API_KEY is missing. Add it to your .env file and restart the server."
        )
    return api_key


def _make_request(endpoint: str, params: dict, include_units: bool = True) -> dict:
    api_key = _get_api_key()

    request_params = {**params, "appid": api_key}
    if include_units:
        request_params["units"] = "metric"

    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", params=request_params, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in {401, 403}:
            raise WeatherServiceError(
                "Weather API key is invalid or unauthorized. Verify WEATHER_API_KEY and restart the server."
            ) from exc
        if status_code == 404:
            raise WeatherServiceError("Location not found. Check the city/ZIP and try again.") from exc
        if status_code == 429:
            raise WeatherServiceError("Weather API limit reached. Please wait a bit and try again.") from exc
        raise WeatherServiceError("Weather service returned an unexpected error.") from exc
    except requests.RequestException as exc:
        raise WeatherServiceError(
            "Unable to reach weather service. Check your internet connection and try again."
        ) from exc

    return response.json()


def _make_geo_request(endpoint: str, params: dict) -> list:
    api_key = _get_api_key()

    request_params = {**params, "appid": api_key}
    try:
        response = requests.get(f"{GEO_BASE_URL}/{endpoint}", params=request_params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherServiceError("Unable to load search suggestions right now.") from exc

    return response.json()


def _c_to_f(value_celsius: float) -> float:
    return (value_celsius * 9 / 5) + 32


def _format_temp(temp_celsius: float, unit: str) -> float:
    return round(_c_to_f(temp_celsius), 1) if unit == "fahrenheit" else round(temp_celsius, 1)


def _aqi_label(aqi: int) -> str:
    labels = {
        1: "Good",
        2: "Fair",
        3: "Moderate",
        4: "Poor",
        5: "Very Poor",
    }
    return labels.get(aqi, "Unknown")


def _slot_local_time(slot: dict, timezone_offset_seconds: int) -> str:
    dt_value = int(slot.get("dt", 0)) + timezone_offset_seconds
    return datetime.utcfromtimestamp(dt_value).strftime("%H:%M")


def _wardrobe_tip(temp_c: float, rain_expected: bool, wind_speed: float) -> str:
    if rain_expected:
        return "Carry a light waterproof jacket and umbrella."
    if temp_c >= 30:
        return "Light cotton clothing, hydration, and sun protection are recommended."
    if temp_c <= 12:
        return "Layer up with a warm top and a wind-resistant outer layer."
    if wind_speed >= 8:
        return "Use a light windbreaker for comfort outdoors."
    return "Comfortable casual wear should be fine for most of the day."


def _fetch_weather_payload(location_params: dict) -> tuple[dict, bool, datetime, int]:
    cache_identifier = "|".join(f"{k}:{v}" for k, v in sorted(location_params.items()))
    cache_key = f"weather:{cache_identifier}"

    cached_payload = cache.get(cache_key)
    from_cache = cached_payload is not None

    if cached_payload is None:
        current_data = _make_request("weather", location_params)
        forecast_data = _make_request("forecast", location_params)
        coords = current_data.get("coord", {})
        aqi_data = None
        if coords.get("lat") is not None and coords.get("lon") is not None:
            aqi_data = _make_request(
                "air_pollution",
                {"lat": coords.get("lat"), "lon": coords.get("lon")},
                include_units=False,
            )

        cached_payload = {
            "current": current_data,
            "forecast": forecast_data,
            "aqi": aqi_data,
            "fetched_at": timezone.now().isoformat(),
        }
        cache.set(cache_key, cached_payload, timeout=settings.WEATHER_CACHE_TIMEOUT)

    fetched_at = datetime.fromisoformat(cached_payload["fetched_at"])
    if timezone.is_naive(fetched_at):
        fetched_at = timezone.make_aware(fetched_at, timezone.utc)
    cache_age_seconds = max(0, int((timezone.now() - fetched_at).total_seconds()))

    return cached_payload, from_cache, fetched_at, cache_age_seconds


def get_location_suggestions(query: str, limit: int = 6) -> list[dict]:
    value = query.strip()
    if len(value) < 2:
        return []

    locations = _make_geo_request("direct", {"q": value, "limit": limit})
    suggestions = []
    for item in locations:
        name = item.get("name")
        country = item.get("country")
        if not name or not country:
            continue

        state = item.get("state")
        label = f"{name}, {state}, {country}" if state else f"{name}, {country}"
        suggestions.append(
            {
                "label": label,
                "name": name,
                "lat": item.get("lat"),
                "lon": item.get("lon"),
            }
        )
    return suggestions


def get_weather_data(
    query: str | None = None,
    unit: str = "celsius",
    lat: str | None = None,
    lon: str | None = None,
) -> dict:
    unit = unit if unit in {"celsius", "fahrenheit"} else "celsius"
    location_params = _build_location_params(query=query, lat=lat, lon=lon)

    cached_payload, from_cache, fetched_at, cache_age_seconds = _fetch_weather_payload(location_params)

    current = cached_payload["current"]
    forecast = cached_payload["forecast"]

    days = {}
    trend_labels = []
    trend_highs = []
    trend_lows = []

    for item in forecast.get("list", []):
        date_key = item.get("dt_txt", "").split(" ")[0]
        if not date_key:
            continue

        day_entry = days.setdefault(
            date_key,
            {
                "date": date_key,
                "temp_min": item["main"]["temp_min"],
                "temp_max": item["main"]["temp_max"],
                "description": item["weather"][0]["description"],
                "icon": item["weather"][0]["icon"],
            },
        )

        day_entry["temp_min"] = min(day_entry["temp_min"], item["main"]["temp_min"])
        day_entry["temp_max"] = max(day_entry["temp_max"], item["main"]["temp_max"])

        hour = datetime.utcfromtimestamp(item["dt"]).hour
        if hour == 12:
            day_entry["description"] = item["weather"][0]["description"]
            day_entry["icon"] = item["weather"][0]["icon"]

    forecast_days = []
    for date_key, item in sorted(days.items())[:7]:
        parsed_date = datetime.strptime(date_key, "%Y-%m-%d")
        formatted_high = _format_temp(item["temp_max"], unit)
        formatted_low = _format_temp(item["temp_min"], unit)
        forecast_days.append(
            {
                "weekday": parsed_date.strftime("%a"),
                "date": parsed_date.strftime("%b %d"),
                "temp_min": formatted_low,
                "temp_max": formatted_high,
                "description": item["description"].capitalize(),
                "icon": item["icon"],
            }
        )
        trend_labels.append(parsed_date.strftime("%a"))
        trend_highs.append(formatted_high)
        trend_lows.append(formatted_low)

    try:
        aqi_value = None
        if cached_payload.get("aqi") and cached_payload["aqi"].get("list"):
            aqi_value = cached_payload["aqi"]["list"][0].get("main", {}).get("aqi")

        current_weather = {
            "city": current["name"],
            "country": current["sys"].get("country", ""),
            "temperature": _format_temp(current["main"]["temp"], unit),
            "feels_like": _format_temp(current["main"]["feels_like"], unit),
            "humidity": current["main"]["humidity"],
            "wind_speed": round(current["wind"].get("speed", 0), 1),
            "pressure": current["main"].get("pressure"),
            "visibility": round(current.get("visibility", 0) / 1000, 1),
            "sunrise": datetime.utcfromtimestamp(current["sys"].get("sunrise", 0)).strftime("%H:%M"),
            "sunset": datetime.utcfromtimestamp(current["sys"].get("sunset", 0)).strftime("%H:%M"),
            "description": current["weather"][0]["description"].capitalize(),
            "icon": current["weather"][0]["icon"],
            "unit": unit,
            "unit_symbol": "F" if unit == "fahrenheit" else "C",
            "lat": current.get("coord", {}).get("lat"),
            "lon": current.get("coord", {}).get("lon"),
            "aqi": aqi_value,
            "aqi_label": _aqi_label(aqi_value) if aqi_value else "Unavailable",
        }
    except (KeyError, IndexError, TypeError) as exc:
        raise WeatherServiceError("Weather data format was unexpected. Please try again.") from exc

    return {
        "current": current_weather,
        "forecast": forecast_days,
        "meta": {
            "from_cache": from_cache,
            "cache_age_seconds": cache_age_seconds,
            "updated_at": fetched_at,
        },
        "trend": {
            "labels": trend_labels,
            "highs": trend_highs,
            "lows": trend_lows,
        },
    }


def get_feature_insights(
    query: str | None = None,
    lat: str | None = None,
    lon: str | None = None,
    compare_query: str | None = None,
) -> dict:
    location_params = _build_location_params(query=query, lat=lat, lon=lon)
    payload, _, _, _ = _fetch_weather_payload(location_params)

    current = payload["current"]
    forecast_list = payload["forecast"].get("list", [])
    next_slots = forecast_list[:8]
    timezone_offset = int(current.get("timezone", 0))

    rain_slot = None
    for slot in next_slots:
        weather_main = slot.get("weather", [{}])[0].get("main", "").lower()
        pop = float(slot.get("pop", 0))
        if weather_main in {"rain", "thunderstorm", "drizzle"} or pop >= 0.45:
            rain_slot = slot
            break

    if rain_slot:
        rain_prob = int(round(float(rain_slot.get("pop", 0)) * 100))
        rain_alert = (
            f"Likely rain around {_slot_local_time(rain_slot, timezone_offset)} local time "
            f"with ~{rain_prob}% probability."
        )
    else:
        rain_alert = "No strong rain signal in the next 24 hours."

    current_temp = float(current.get("main", {}).get("temp", 0))
    wind_speed = float(current.get("wind", {}).get("speed", 0))
    humidity = int(current.get("main", {}).get("humidity", 0))
    current_main = current.get("weather", [{}])[0].get("main", "").lower()

    commute_score = 100
    commute_score -= int(abs(current_temp - 22) * 2)
    commute_score -= int(max(0, wind_speed - 4) * 3)
    commute_score -= int(max(0, humidity - 70) * 0.5)
    if current_main in {"rain", "thunderstorm", "drizzle", "snow"}:
        commute_score -= 18
    commute_score = max(12, min(98, commute_score))

    if commute_score >= 80:
        commute_text = "Comfortable commute conditions expected."
    elif commute_score >= 60:
        commute_text = "Moderate commute comfort. Consider a light layer or umbrella."
    else:
        commute_text = "Commute may feel rough due to weather. Plan extra buffer time."

    best_slot = None
    best_score = -999
    for slot in next_slots:
        temp = float(slot.get("main", {}).get("temp", 0))
        wind = float(slot.get("wind", {}).get("speed", 0))
        pop = float(slot.get("pop", 0))
        weather_main = slot.get("weather", [{}])[0].get("main", "").lower()

        score = 0
        score -= abs(temp - 24) * 2
        score -= wind * 1.5
        score -= pop * 70
        if weather_main in {"rain", "thunderstorm", "drizzle", "snow"}:
            score -= 18

        if score > best_score:
            best_score = score
            best_slot = slot

    if best_slot:
        outdoor_text = (
            f"Best outdoor window: {_slot_local_time(best_slot, timezone_offset)} local time "
            f"(temp {round(float(best_slot.get('main', {}).get('temp', 0)), 1)}C)."
        )
    else:
        outdoor_text = "No clear outdoor window detected in the next 24 hours."

    aqi_value = None
    if payload.get("aqi") and payload["aqi"].get("list"):
        aqi_value = payload["aqi"]["list"][0].get("main", {}).get("aqi")
    aqi_label = _aqi_label(aqi_value) if aqi_value else "Unknown"

    aqi_tips = {
        "Good": "Air quality is good. Outdoor exercise is generally fine.",
        "Fair": "Air quality is acceptable. Sensitive groups should monitor symptoms.",
        "Moderate": "Limit prolonged intense outdoor activity if you are sensitive.",
        "Poor": "Prefer shorter outdoor exposure and consider a mask in busy streets.",
        "Very Poor": "Avoid strenuous outdoor activity and keep windows closed when possible.",
    }
    aqi_tip = aqi_tips.get(aqi_label, "Air quality insight is currently unavailable.")

    rain_expected = rain_slot is not None
    wardrobe_text = _wardrobe_tip(current_temp, rain_expected, wind_speed)

    compare_text = "Add a second city name to compare temperatures."
    if compare_query and compare_query.strip():
        compare_params = _build_location_params(query=compare_query.strip())
        compare_payload, _, _, _ = _fetch_weather_payload(compare_params)
        compare_current = compare_payload["current"]
        temp_delta = round(float(current.get("main", {}).get("temp", 0)) - float(compare_current.get("main", {}).get("temp", 0)), 1)
        if temp_delta > 0:
            direction = "warmer"
        elif temp_delta < 0:
            direction = "cooler"
        else:
            direction = "about the same temperature as"

        if direction == "about the same temperature as":
            compare_text = (
                f"{current.get('name', 'Current city')} is {direction} {compare_current.get('name', 'comparison city')} right now."
            )
        else:
            compare_text = (
                f"{current.get('name', 'Current city')} is {abs(temp_delta)}C {direction} "
                f"than {compare_current.get('name', 'comparison city')} right now."
            )

    return {
        "rain-alert": {
            "title": "Rain Start Alert",
            "body": rain_alert,
        },
        "commute-score": {
            "title": "Commute Comfort Score",
            "body": f"Score {commute_score}/100. {commute_text}",
        },
        "outdoor-planner": {
            "title": "Outdoor Planner",
            "body": outdoor_text,
        },
        "aq-tips": {
            "title": "Air Quality Tips",
            "body": f"AQI status: {aqi_label}. {aqi_tip}",
        },
        "city-compare": {
            "title": "City Weather Compare",
            "body": compare_text,
        },
        "wardrobe": {
            "title": "Wardrobe Suggestion",
            "body": wardrobe_text,
        },
    }
