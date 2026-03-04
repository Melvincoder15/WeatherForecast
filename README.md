# Weather Forecast (Django)

A weather forecast web app built with Python and Django, with city/ZIP search, location-based insights, and a styled glassmorphism UI.

## Features

### Core weather flow
- Search by city name or ZIP code (for example: `Tokyo`, `10001,us`)
- Current weather display with:
  - Temperature
  - Feels-like temperature
  - Humidity
  - Wind speed
  - Weather icon and description
- 7-day forecast cards
- Celsius/Fahrenheit unit support

### Home page insights panel
- Automatically loads your current-location weather summary (when location permission is granted)
- Shows a prominent "Today's temperature" card
- Interactive feature buttons with live results:
  - Rain Start Alert
  - Commute Comfort Score
  - Outdoor Planner
  - Air Quality Tips
  - City Weather Compare
  - Wardrobe Suggestion
- City compare input appears only for the compare feature

### Search behavior rules
- Manual `Search` requires typing a place
- If `Search` is clicked with empty input, the UI shows: `Type place`
- `Use my location` is a separate flow that submits latitude/longitude

### UI/UX enhancements
- Autocomplete suggestions while typing place names
- Theme toggle button in header (default / storm-cloud blue theme)
- Responsive layout for desktop and mobile
- Better back-navigation handling to prevent stuck buttons

### Caching and performance
- Server-side caching for weather API payloads (default: 15 minutes)
- Client-side caching for fast home summary rendering
- Cached coordinates reused to speed up location summary loading

## Python Libraries Used

Defined in [requirements.txt](./requirements.txt):
- `Django>=5.1,<6.0`
- `requests>=2.32.0`
- `python-dotenv>=1.0.1`

## External Services Used

- OpenWeatherMap APIs:
  - Current weather
  - 5-day/3-hour forecast
  - Air pollution
  - Geocoding (autocomplete suggestions)

## Project Structure

- `weather_project/`
  - `settings.py` - Django config, env loading, cache config, static settings
  - `urls.py` - root URL routing
- `forecast/`
  - `views.py` - page views and JSON endpoints
  - `urls.py` - app routes
  - `services.py` - all weather/geocode/insight service logic
  - `models.py` - placeholder for future persistence
- `templates/forecast/`
  - `base.html` - base layout + header/footer
  - `home.html` - search + current-location insights panel
  - `weather.html` - detailed weather and forecast page
- `static/`
  - `css/style.css` - UI styles and themes
  - `js/app.js` - frontend interactions (autocomplete, geolocation, insights, theme toggle)

## Internal Endpoints

- `GET /` - home page
- `GET /search/` - weather results page
- `GET /autocomplete/?q=...` - location suggestions
- `GET /insights/?q=...` or `?lat=...&lon=...` - feature insight results
- `GET /current-summary/?lat=...&lon=...&unit=celsius|fahrenheit` - home summary data

## Setup

1. Create a virtual environment and activate it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create env file:
   ```bash
   cp .env.example .env
   ```
4. Set your OpenWeather API key in `.env`.
5. Run migrations:
   ```bash
   python manage.py migrate
   ```
6. Start the development server:
   ```bash
   python manage.py runserver
   ```
7. Open:
   - `http://127.0.0.1:8000/`

## Environment Variables

Example values are in [.env.example](./.env.example).

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `WEATHER_API_KEY`
- `WEATHER_CACHE_TIMEOUT`

## Development Check

Run Django checks:
```bash
python manage.py check
```

## Notes

- Geolocation features require browser location permission.
- If static UI changes do not appear immediately, do a hard refresh (`Cmd+Shift+R` / `Ctrl+F5`).
