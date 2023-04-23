from keboola.http_client import HttpClient
from requests.exceptions import HTTPError

BASE_URL = "https://api.weatherapi.com/v1"

ENDPOINT_HISTORY = "history.json"
ENDPOINT_FORECAST = "forecast.json"


class WeatherApiClientException(Exception):
    pass


class WeatherApiClient(HttpClient):
    def __init__(self, token):
        self.token = token
        super().__init__(BASE_URL)

    def get_endpoint(self, endpoint: str, params: dict) -> dict:
        try:
            return self.get(endpoint_path=endpoint, params=params)
        except HTTPError as http_err:
            raise WeatherApiClientException(http_err) from http_err

    def get_forecast(self, location_query: str, days: int) -> dict:
        parameters = {"key": self.token, "q": location_query, "days": days}
        return self.get_endpoint(ENDPOINT_FORECAST, parameters)

    def get_history(self, location_query: str, historical_date: str) -> dict:
        parameters = {"key": self.token, "q": location_query, "dt": historical_date}
        return self.get_endpoint(ENDPOINT_HISTORY, parameters)
