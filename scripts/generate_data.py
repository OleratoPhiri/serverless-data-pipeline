import csv
import random
from datetime import datetime, timedelta

# Cities for our simulated weather sensor network
CITIES = ["Pretoria", "Johannesburg", "Cape Town", "Durban", "Bloemfontein"]


def generate_weather_row(date):
    """
    Generates one row of weather data.
    Intentionally introduces realistic data quality issues:
    - Some temperatures have units attached (need cleaning)
    - Some values are missing entirely
    - Some humidity readings are invalid (negative)
    - Some timestamps use a different format
    """
    city = random.choice(CITIES)

    # Temperature: mix of clean numbers, units-attached, and missing
    temp_roll = random.random()
    if temp_roll < 0.7:
        temperature = round(random.uniform(10, 35), 1)
    elif temp_roll < 0.85:
        temperature = f"{round(random.uniform(10, 35), 1)}°C"  # needs cleaning
    else:
        temperature = ""  # missing value

    # Humidity: mix of valid, invalid negative, and missing
    humidity_roll = random.random()
    if humidity_roll < 0.8:
        humidity = random.randint(20, 95)
    elif humidity_roll < 0.9:
        humidity = -1  # invalid — needs cleaning
    else:
        humidity = ""  # missing value

    # Timestamp: mix of correct format and inconsistent format
    timestamp_roll = random.random()
    if timestamp_roll < 0.85:
        timestamp = date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        timestamp = date.strftime("%d/%m/%Y")  # inconsistent — needs cleaning

    return [city, temperature, humidity, timestamp]


def generate_file(filename, num_rows=20, day_offset=0):
    date = datetime.now() - timedelta(days=day_offset)
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "temperature", "humidity", "timestamp"])
        for _ in range(num_rows):
            writer.writerow(generate_weather_row(date))
    print(f"Created {filename} with {num_rows} rows")


if __name__ == "__main__":
    generate_file("weather_day1.csv", num_rows=20, day_offset=2)
    generate_file("weather_day2.csv", num_rows=20, day_offset=1)
    generate_file("weather_day3.csv", num_rows=20, day_offset=0)
    print("\nAll sample files created!")