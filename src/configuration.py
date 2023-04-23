import dataclasses
import json
from dataclasses import dataclass
from enum import Enum
from typing import List

import dataconf


class ConfigurationBase:
    @staticmethod
    def _convert_private_value(value: str):
        return value.replace('"#', '"pswd_')

    @staticmethod
    def _convert_private_value_inv(value: str):
        if value and value.startswith("pswd_"):
            return value.replace("pswd_", "#", 1)
        else:
            return value

    @classmethod
    def load_from_dict(cls, configuration: dict):
        """
        Initialize the configuration dataclass object from dictionary.
        Args:
            configuration: Dictionary loaded from json configuration.

        Returns:

        """
        json_conf = json.dumps(configuration)
        json_conf = ConfigurationBase._convert_private_value(json_conf)
        return dataconf.loads(json_conf, cls, ignore_unexpected=True)

    @classmethod
    def get_dataclass_required_parameters(cls) -> List[str]:
        """
        Return list of required parameters based on the dataclass definition (no default value)
        Returns: List[str]

        """
        return [cls._convert_private_value_inv(f.name)
                for f in dataclasses.fields(cls)
                if f.default == dataclasses.MISSING
                and f.default_factory == dataclasses.MISSING]


@dataclass
class Authentication(ConfigurationBase):
    pswd_api_token: str


class FetchParameterFrom(str, Enum):
    CONFIG_PARAMETERS = "config_parameters"
    INPUT_TABLE = "input_table"


class RequestType(str, Enum):
    FORECAST = "forecast"
    HISTORY = "history"


@dataclass
class FetchingSettings(ConfigurationBase):
    fetch_parameter_from: FetchParameterFrom = FetchParameterFrom.CONFIG_PARAMETERS
    request_type: RequestType = RequestType.FORECAST
    location_query: str = "New York"
    forecast_days: int = 10
    historical_date: str = "2022-09-09"
    continue_on_failure: bool = True


class LoadType(str, Enum):
    FULL_LOAD = "full_load"
    INCREMENTAL_LOAD = "incremental_load"


@dataclass
class DestinationSettings(ConfigurationBase):
    load_type: LoadType = LoadType.INCREMENTAL_LOAD


@dataclass
class Configuration(ConfigurationBase):
    authentication: Authentication
    fetching_settings: FetchingSettings
    destination_settings: DestinationSettings
