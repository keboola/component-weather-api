import csv
import logging
import time
from typing import Iterator

import dateparser
from keboola.component.base import ComponentBase, sync_action
from keboola.component.dao import TableDefinition
from keboola.component.exceptions import UserException

from client import WeatherApiClient, WeatherApiClientException
from configuration import Configuration, FetchParameterFrom, RequestType, LoadType
from table_handler import TableHandler


class Component(ComponentBase):
    def __init__(self):
        self._configuration: Configuration
        self.client: WeatherApiClient
        self._table_handlers = {}
        self.extraction_start = int(time.time())
        super().__init__()

    def run(self) -> None:
        self._init_configuration()
        self._init_client()
        self._init_table_handlers()

        for fetching_parameters in self.get_fetching_parameters():
            logging.info(f"Fetching data with parameters : {fetching_parameters}")
            self.fetch_and_write_data_with_parameters(fetching_parameters)

        self.close_table_handlers()

    def _init_configuration(self) -> None:
        self.validate_configuration_parameters(Configuration.get_dataclass_required_parameters())
        self._configuration: Configuration = Configuration.load_from_dict(self.configuration.parameters)

    def _init_client(self) -> None:
        self.client = WeatherApiClient(self._configuration.authentication.pswd_api_token)

    def _init_table_handlers(self) -> None:
        self._init_table_handler_by_schema_name("weather_daily")
        self._init_table_handler_by_schema_name("weather_hourly")
        self._init_table_handler_by_schema_name("weather_astronomical")

        if self._configuration.fetching_settings.continue_on_failure:
            self._init_table_handler_by_schema_name("failed_fetches")

    def _init_table_handler_by_schema_name(self, schema_name: str) -> None:
        schema = self.get_table_schema_by_name(schema_name)
        table_definition = self.create_out_table_definition_from_schema(schema)

        if self._configuration.destination_settings.load_type == LoadType.INCREMENTAL_LOAD:
            table_definition.incremental = True

        file = open(table_definition.full_path, 'w')
        writer = csv.DictWriter(file, fieldnames=table_definition.columns)
        self._table_handlers[schema_name] = TableHandler(table_definition, file, writer)

    def close_table_handlers(self) -> None:
        for table_handler in self._table_handlers:
            self._table_handlers[table_handler].close()
            self.write_manifest(self._table_handlers[table_handler].table_definition)

    def fetch_and_write_data_with_parameters(self, fetching_parameters: dict) -> None:
        request_type = self._configuration.fetching_settings.request_type
        try:
            if request_type == RequestType.HISTORY:
                self.fetch_and_write_history_data(**fetching_parameters)
            elif request_type == RequestType.FORECAST:
                self.fetch_and_write_forecast_data(**fetching_parameters)
        except (TypeError, UserException, ValueError) as failed_fetch_exc:
            if self._configuration.fetching_settings.continue_on_failure:
                self.write_error(fetching_parameters, failed_fetch_exc)
            else:
                raise UserException(failed_fetch_exc) from failed_fetch_exc

    def get_fetching_parameters(self) -> Iterator:
        if self.fetch_from_config_params():
            return self.get_fetching_parameters_from_configuration()
        else:
            return self.get_fetching_parameters_from_input_table()

    def fetch_from_config_params(self):
        return self._configuration.fetching_settings.fetch_parameter_from == FetchParameterFrom.CONFIG_PARAMETERS

    def get_fetching_parameters_from_configuration(self) -> Iterator:
        request_type = self._configuration.fetching_settings.request_type
        location = self._configuration.fetching_settings.location_query
        fetching_parameters = {"location": location}

        if request_type == RequestType.FORECAST:
            forecast_days = self._configuration.fetching_settings.forecast_days
            fetching_parameters["forecast_days"] = forecast_days

        if request_type == RequestType.HISTORY:
            historical_date_raw = self._configuration.fetching_settings.historical_date
            historical_date = self.parse_date(historical_date_raw)
            fetching_parameters["historical_date"] = historical_date
        yield fetching_parameters

    def get_fetching_parameters_from_input_table(self) -> Iterator:
        input_table = self._get_single_input_table()
        with open(input_table.full_path) as in_table:
            reader = csv.DictReader(in_table)
            for row in reader:
                yield self.process_input_row(row)

    def process_input_row(self, row: dict):
        request_type = self._configuration.fetching_settings.request_type

        if "location" in row:
            location = row["location"]
        elif "latitude" in row and "longitude" in row:
            location = f"{row['latitude']},{row['longitude']}"
        else:
            raise UserException("Input Table Error : Input table must contain either a 'location' column "
                                "or a 'latitude' and 'longitude' column")
        fetching_parameters = {"location": location}

        if "forecast_days" in row and request_type == RequestType.FORECAST:
            try:
                fetching_parameters["forecast_days"] = int(row['forecast_days'])
            except ValueError:
                logging.warning(f"Could not parse {row['forecast_days']} to int, falling back to default '10'")
                fetching_parameters["forecast_days"] = 10
        elif request_type == RequestType.FORECAST:
            fetching_parameters["forecast_days"] = 10

        if "historical_date" in row and request_type == RequestType.HISTORY:
            try:
                historical_date = self.parse_date(row['historical_date'])
            except UserException:
                historical_date = row['historical_date']
            fetching_parameters["historical_date"] = historical_date

        return fetching_parameters

    def _get_single_input_table(self) -> TableDefinition:
        input_tables = self.get_input_tables_definitions()
        if len(input_tables) != 1:
            raise UserException("Input Table Error : Only 1 table should be specified in the input mapping")
        return input_tables[0]

    def fetch_and_write_history_data(self, location: str, historical_date: str) -> None:
        historical_forecast = self.get_history_data(location, historical_date)
        self.write_forecast_data(historical_forecast)

    def get_history_data(self, location: str, historical_date: str) -> dict:
        try:
            return self.client.get_history(location, historical_date)
        except WeatherApiClientException as weather_api_exc:
            message = self.get_api_exception_message(weather_api_exc)
            raise UserException(message) from weather_api_exc

    def fetch_and_write_forecast_data(self, location: str, forecast_days: int) -> None:
        forecast = self.get_forecast_data(location, forecast_days)
        self.write_forecast_data(forecast)

    def get_forecast_data(self, location: str, forecast_days: int) -> dict:
        try:
            return self.client.get_forecast(location, forecast_days)
        except WeatherApiClientException as weather_api_exc:
            message = self.get_api_exception_message(weather_api_exc)
            raise UserException(message) from weather_api_exc

    def get_api_exception_message(self, weather_api_exc: WeatherApiClientException) -> str:
        try:
            message = weather_api_exc.args[0].args[0]
            if "403" in weather_api_exc.args[0].args[0]:
                message = "Authorization Error : Invalid API token"
            elif "400" in weather_api_exc.args[0].args[0]:
                if self._configuration.fetching_settings.request_type == RequestType.FORECAST:
                    message = "Parameters Error : Invalid Location or Days parameter"
                elif self._configuration.fetching_settings.request_type == RequestType.HISTORY:
                    message = "Parameters Error : Invalid Location or Historical Date parameter"
            return message
        except (IndexError, KeyError):
            return f"Error : {weather_api_exc}"

    def write_forecast_data(self, forecast: dict) -> None:
        daily_data, hourly_data, astro_data = self.parse_forecast_data(forecast)
        self._table_handlers["weather_daily"].write_rows(daily_data)
        self._table_handlers["weather_hourly"].write_rows(hourly_data)
        self._table_handlers["weather_astronomical"].write_rows(astro_data)

    def write_error(self, parameters: dict, error: Exception) -> None:
        self._table_handlers["failed_fetches"].write_row({"parameters": str(parameters),
                                                          "error": error,
                                                          "fetching_timestamp": self.extraction_start})

    def parse_forecast_data(self, forecast: dict) -> tuple[list[dict], list[dict], list[dict]]:
        daily = []
        hourly = []
        astro = []

        latitude = forecast["location"]["lat"]
        longitude = forecast["location"]["lon"]
        location_name = forecast["location"]["name"]
        forecast_days = forecast["forecast"]["forecastday"]

        for forecast_day in forecast_days:
            date = forecast_day["date"]
            condition = forecast_day["day"].pop("condition")["text"]
            daily.append({"latitude": latitude,
                          "longitude": longitude,
                          "location_name": location_name,
                          "extraction_timestamp": self.extraction_start,
                          "date": date,
                          "condition": condition,
                          **forecast_day["day"]})

            astro.append({"latitude": latitude,
                          "longitude": longitude,
                          "location_name": location_name,
                          "extraction_timestamp": self.extraction_start,
                          "date": date,
                          **forecast_day["astro"]})

            for hour in forecast_day["hour"]:
                date = forecast_day["date"]
                condition = hour.pop("condition")["text"]
                hourly.append({"latitude": latitude,
                               "longitude": longitude,
                               "location_name": location_name,
                               "extraction_timestamp": self.extraction_start,
                               "date": date,
                               "condition": condition,
                               **hour})

        return daily, hourly, astro

    @staticmethod
    def parse_date(date_str: str) -> str:
        try:
            date_obj = dateparser.parse(date_str)
            if date_obj is None:
                raise ValueError("Invalid date string")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError as e:
            raise UserException(f"Parameters Error : Could not parse to date : {date_str}") from e

    @sync_action("testConnection")
    def test_connection(self):
        self._init_configuration()
        self._init_client()
        try:
            self.client.get_forecast("Paris", 1)
        except WeatherApiClientException as weather_api_exc:
            raise UserException("Authorization Error : Invalid API token") from weather_api_exc


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
