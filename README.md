# AIR INDIA — Smart Pan-India Air Quality Monitoring Platform

A Flask + SQLite + Leaflet + Chart.js project for a scalable air-quality monitoring dashboard across Indian cities.

## Main features

- 🇮🇳 Pan-India state → city → monitoring station selection
- 🗺️ Live India monitoring map with AQI markers and heatmap
- 📊 MQ2 / MQ3 / MQ135 historical analytics
- 📊 Multi-station MQ sensor comparison
- 🛡️ Project-defined AirSafe Score
- 🔧 Sensor health scoring for MQ2, MQ3 and MQ135
- ⚠️ Sensor anomaly detection
- 🚨 Possible pollution-event detection from MQ sensor spikes
- 🌤️ Best time to go outside from recent station history
- 🔍 Explain My AQI
- 🤖 Local Air AI Assistant using selected-station data
- 🛣️ Clean Air Route candidate using road alternatives and nearby station AQI
- 🔔 AQI alerts
- 📈 Six-hour AQI outlook
- 📍 Nearest station using browser location
- 📥 CSV export
- 🔌 IoT POST endpoint at `/data`

## Important data note

The included station readings are demo/simulated data for project demonstration. The AirSafe Score, route exposure indicator, sensor health, anomaly detection and event detection are project-defined analytics and should not be presented as official government measurements.

The interface intentionally does not display PM2.5/PM10 cards or graphs. The existing backend keeps its legacy pollutant fields because the current AQI calculation and stored demo data use them; they are not exposed in the new dashboard UI.

## Run

```bash
python -m pip install -r requirements.txt
python app.py
```

Open:

`http://127.0.0.1:5000`

## Demo admin

Email: `admin@airindia.local`

Password: `admin123`

## Clean Air Route

The route tool uses OpenStreetMap Nominatim for geocoding and the public OSRM routing service for road alternatives. An estimated route exposure indicator is calculated from the nearest available station readings. It is a project feature, not an official pollution-exposure measurement.
