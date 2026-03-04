from django.urls import path

from . import views

app_name = "forecast"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search_weather, name="search_weather"),
    path("autocomplete/", views.autocomplete_locations, name="autocomplete"),
    path("insights/", views.feature_insights, name="feature_insights"),
    path("current-summary/", views.current_summary, name="current_summary"),
]
