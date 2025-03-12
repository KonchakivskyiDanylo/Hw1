import datetime as dt
import requests
import json
from flask import Flask, jsonify, request
from openai import OpenAI

import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not API_TOKEN or not WEATHER_API_KEY or not OPENAI_API_KEY:
    raise ValueError("Missing API keys. Please set them in the .env file.")
app = Flask(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


def get_weather(location: str, date):
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/{date}"

    params = {
        'unitGroup': 'metric',
        'key': WEATHER_API_KEY,
        'contentType': 'json',
    }

    response = requests.get(url, params=params)

    if response.status_code == requests.codes.ok:
        data = response.json()
        day_data = data.get('days', [{}])[0]

        # Format the weather data as a flat dictionary
        weather_data = {
            "min_temp": round(day_data.get('tempmin', 0), 1),  # Minimum temperature (°C)
            "avg_temp": round(day_data.get('temp', 0), 1),  # Average temperature (°C)
            "max_temp": round(day_data.get('tempmax', 0), 1),  # Maximum temperature (°C)
            "feels_like": round(day_data.get('feelslike', 0), 1),  # Perceived temperature (°C)

            "rain_probability": day_data.get('precipprob', 0),  # Chance of precipitation (%)
            "total_rainfall_mm": round(day_data.get('precip', 0), 1),  # Total precipitation amount (mm)

            "max_wind_gust_kmh": round(day_data.get('windgust', 0), 1),  # Maximum wind gust (km/h)
            "avg_wind_speed_kmh": round(day_data.get('windspeed', 0), 1),  # Average wind speed (km/h)
            "wind_direction": round(day_data.get('winddir', 0), 1),  # Wind direction (degrees)

            "humidity": round(day_data.get('humidity', 0), 1),  # Relative humidity (%)
            "dew_point": round(day_data.get('dew', 0), 1),  # Dew point temperature (°C)
            "pressure_hpa": round(day_data.get('pressure', 0), 1),  # Atmospheric pressure (hPa)

            "uv_index": round(day_data.get('uvindex', 0), 1),  # UV radiation index
            "cloud_cover": round(day_data.get('cloudcover', 0), 1),  # Cloud coverage (%)
            "visibility_km": round(day_data.get('visibility', 0), 1),  # Visibility distance (km)

            "description": day_data.get('description', '')}  # Weather description

        return weather_data
    else:
        raise InvalidUsage(response.text, status_code=response.status_code)


def get_clothing_recommendation(weather_data, location):
    prompt = f"""
        Проаналізуй цю інформацію про погоду в {location}:
        Мінімальна температура: {weather_data['min_temp']}°C
        Середня температура: {weather_data['avg_temp']}°C
        Максимальна температура: {weather_data['max_temp']}°C
        Відчувається як: {weather_data['feels_like']}°C
        Ймовірність опадів: {weather_data['rain_probability']}%
        Кількість опадів: {weather_data['total_rainfall_mm']} мм
        Швидкість вітру: {weather_data['avg_wind_speed_kmh']} км/год
        Пориви вітру: {weather_data['max_wind_gust_kmh']} км/год
        Напрямок вітру: {weather_data['wind_direction']}°
        Атмосферний тиск: {weather_data['pressure_hpa']} гПа
        Вологість: {weather_data['humidity']}%
        Індекс УФ: {weather_data['uv_index']}
        Хмарність: {weather_data['cloud_cover']}%
        Видимість: {weather_data['visibility_km']} км
        Опис погоди: {weather_data['description']}

        Порадь, що краще одягнути сьогодні, враховуючи ці погодні умови.
        Також вкажи, чи є якісь застереження (наприклад, погана видимість, сильний вітер, екстремальна температура тощо).
        Дай відповідь на такі питання:
        1. Як одягатися в цей день та які конкретно речі краще одягнути (куртка, светр, футболка і т.д.)?
        2. Які застереження щодо здоров'я варто врахувати через погодні умови?

        Надай відповідь українською мовою у форматі JSON з полями:
        "clothing": [список речей],
        "health_warnings": [застереження для здоров'я]
        """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        recommendation = response.choices[0].message.content
        try:
            recommendation_json = json.loads(recommendation)
            return recommendation_json
        except json.JSONDecodeError:
            return {
                "recommendation": recommendation,
            }

    except Exception as e:
        return {
            "clothing_recommendation": "Не вдалося отримати рекомендації щодо одягу",
            "warnings": f"Помилка: {str(e)}"
        }


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/")
def home_page():
    return "<p><h2>KMA HW1: python Saas.</h2></p>"


@app.route("/get/weather", methods=["POST"])
def joke_endpoint():
    json_data = request.get_json()
    if json_data.get("token") is None:
        raise InvalidUsage("token is required", status_code=400)
    token = json_data.get("token")
    if token != API_TOKEN:
        raise InvalidUsage("wrong API token", status_code=403)
    if json_data.get("location") is None:
        raise InvalidUsage("location is required", status_code=400)
    if json_data.get("date") is None:
        raise InvalidUsage("date is required", status_code=400)
    location = json_data.get("location")
    date = json_data.get("date")
    requester_name = json_data.get("requester_name", "Unknown")

    weather = get_weather(location, date)
    ai_recommendations = get_clothing_recommendation(weather, location)

    return jsonify({
        "requester_name": requester_name,
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": location,
        "date": date,
        "weather": weather,
        "ai_recommendations": ai_recommendations
    })
