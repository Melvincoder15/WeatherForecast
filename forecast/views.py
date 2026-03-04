from django.http import JsonResponse
from django.shortcuts import render

from .services import (
    WeatherServiceError,
    get_feature_insights,
    get_location_suggestions,
    get_weather_data,
)


def home(request):
    return render(request, "forecast/home.html")


def autocomplete_locations(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    try:
        results = get_location_suggestions(query=query)
    except WeatherServiceError:
        return JsonResponse({"results": []})

    return JsonResponse({"results": results})


def feature_insights(request):
    query = request.GET.get("q", "").strip()
    lat = request.GET.get("lat", "").strip()
    lon = request.GET.get("lon", "").strip()
    compare = request.GET.get("compare", "").strip()

    if not query and not (lat and lon):
        return JsonResponse({"error": "Enter a city/ZIP or use current location first."}, status=400)

    try:
        results = get_feature_insights(
            query=query or None,
            lat=lat or None,
            lon=lon or None,
            compare_query=compare or None,
        )
    except WeatherServiceError as exc:
        return JsonResponse({"error": exc.user_message}, status=400)

    return JsonResponse({"results": results})


def current_summary(request):
    lat = request.GET.get("lat", "").strip()
    lon = request.GET.get("lon", "").strip()
    unit = request.GET.get("unit", "celsius").strip().lower()

    if not (lat and lon):
        return JsonResponse({"error": "Latitude and longitude are required."}, status=400)

    try:
        weather_data = get_weather_data(query=None, unit=unit, lat=lat, lon=lon)
    except WeatherServiceError as exc:
        return JsonResponse({"error": exc.user_message}, status=400)

    current = weather_data["current"]
    return JsonResponse(
        {
            "city": current["city"],
            "country": current["country"],
            "temperature": current["temperature"],
            "unit_symbol": current["unit_symbol"],
            "description": current["description"],
        }
    )


def search_weather(request):
    query = request.GET.get("q", "").strip()
    unit = request.GET.get("unit", "celsius").strip().lower()
    lat = request.GET.get("lat", "").strip()
    lon = request.GET.get("lon", "").strip()
    use_location = request.GET.get("use_location", "0").strip() == "1"

    if not query and not use_location:
        return render(
            request,
            "forecast/home.html",
            {
                "error": "Type place",
                "selected_unit": unit,
            },
        )

    if use_location and not (lat and lon):
        return render(
            request,
            "forecast/home.html",
            {
                "error": "Unable to get your location. Please try again.",
                "selected_unit": unit,
            },
        )

    try:
        weather_data = get_weather_data(query=query, unit=unit, lat=lat or None, lon=lon or None)
    except WeatherServiceError as exc:
        return render(
            request,
            "forecast/home.html",
            {
                "error": exc.user_message,
                "query": query,
                "selected_unit": unit,
            },
        )

    return render(
        request,
        "forecast/weather.html",
        {
            "query": query or weather_data["current"]["city"],
            "current": weather_data["current"],
            "forecast": weather_data["forecast"],
            "meta": weather_data["meta"],
            "trend": weather_data["trend"],
        },
    )
