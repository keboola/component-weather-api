[Weather API](https://weatherapi.com) is a service that provides data of Real Time, Forecasted, Future, Marine and Historical Weather
This component enables users to extract forecast and historical weather data from the [Weather API](https://weatherapi.com).

If the **Parameters From** is set to **Configuration Parameters** set the fetching parameters in the configuration parameters.

If the **Parameters From** is set to **Using An Input Table**, a single input table can be used to set parameters for fetching.

* The table must contain a 'location' column, or a 'latitude' and 'longitude' column to define the location to fetch for.
* If Request Type is set to 'forecast', a 'forecast_days' column can be added, that defines the 'forecast_days' from the configuration, If it is not added, the 'forecast_days' defaults to 10.
* If Request Type is set to 'history', a 'historical_date' column must be added, that defines the 'historical_date' from the configuration.

Each row in the input table is a single request to the API.