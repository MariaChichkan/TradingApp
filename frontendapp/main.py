import sys
sys.path.insert(0, "../utils")

import pandas as pd
import datetime
import redis
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from dash import Dash, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from settings import TRADING_INSTRUMENTS_WITH_NAMES, PSQL_CLIENT, PSQL_DB, REDIS_CLIENT, \
                     REDIS_RETENTION_PERIOD, _logging
from db_orm import TradingPrices



psql_url = \
    f"postgresql://{PSQL_CLIENT.USER}:{PSQL_CLIENT.PASSWORD}@" + \
    f"{PSQL_CLIENT.HOST}{':' + PSQL_CLIENT.PORT if not PSQL_CLIENT.PORT in ['False', False] else ''}" + \
    f"/{PSQL_DB}"

psql_engine = create_engine(psql_url, echo=True)

Session = sessionmaker(bind=psql_engine)
redis_url = f"redis://{REDIS_CLIENT.HOST}:{REDIS_CLIENT.PORT}"
redis = redis.from_url(redis_url, password=REDIS_CLIENT.PASSWORD,
                               encoding='utf-8', decode_responses=True)

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


my_text = dcc.Markdown(children='# Trading instruments charts')
dropdown = dcc.Dropdown(TRADING_INSTRUMENTS_WITH_NAMES,  multi=True, placeholder="Select an instrument",)
selected_instruments = dcc.Markdown(children='')
historical_data = dcc.Store(id='historical-data', data={})
up_to_date_data = dcc.Store(id='up-to-date-data', data={})
button = html.Button("Show instrument's prices", id='show-secret', n_clicks = 0)
graph = dcc.Graph(id="time-series-chart", figure={})
interval = dcc.Interval(
    id="latest_prices",
    interval=1*1000,  # increment the counter n_intervals every interval milliseconds
    n_intervals=0)
app.layout = dbc.Container([my_text, html.Br(), dropdown, button, selected_instruments,  graph, interval, historical_data, up_to_date_data ])

logger = _logging()

# Load historical data for selected instruments into memory.
def get_historical_data(selected_instruments, date_from=None, date_to=None):
    if not date_to:
        date_to = datetime.datetime.now() - datetime.timedelta(hours=2) # because of postgresql time settings
    if not date_from:
        date_from = date_to - datetime.timedelta(minutes=10)

    filters = []
    if len(selected_instruments) > 0:
        filters.append(TradingPrices.instrument_id.in_(selected_instruments))
    filters.append(TradingPrices.created_at >= date_from)
    filters.append(TradingPrices.created_at <= date_to)
    with Session() as session:
        df_instrument_prices = pd.read_sql(session.query(TradingPrices).filter(and_(*filters)).statement, psql_engine)

    df_instrument_prices["created_at"] = df_instrument_prices["created_at"].apply(lambda x: x.replace(microsecond=0))
    df_instrument_prices = df_instrument_prices.sort_values(by=["created_at", "instrument_id"])
    logger.info(f"Got historical data for instruments: {selected_instruments}")
    return df_instrument_prices


def get_latest_prices(instruments=[], prev_time=None):
    current_time = int(datetime.datetime.now().timestamp() * 1000)
    if not prev_time:
        prev_time = current_time - REDIS_RETENTION_PERIOD * 60000  # Each minute equals 60000 ms

    # Get latest prices of selected trading_instruments from redis
    if len(instruments) > 0:
        ts = redis.execute_command("TS.MRANGE", prev_time, current_time, 'FILTER',
                                              'type=trading_instruments', f'name=({",".join(instruments)})')
        logger.info(f"Got latest instrument prices for instruments {instruments} from Redis")
    else:
        ts = redis.execute_command("TS.MRANGE", prev_time, current_time, 'FILTER', 'type=trading_instruments')
        logger.info(f"Got latest instrument prices for all instruments from Redis")

    df_lst = []
    for timeseries in ts:
        df = pd.DataFrame(timeseries[2], columns=["created_at", 'price'])
        df["instrument_id"] = timeseries[0]
        df_lst.append(df)
    df_latest_prices = pd.concat(df_lst, ignore_index=True)
    df_latest_prices['price'] = df_latest_prices['price'].astype("int")
    df_latest_prices["created_at"] = pd.to_datetime(df_latest_prices["created_at"], unit='ms')
    df_latest_prices["created_at"] = df_latest_prices["created_at"].apply(lambda x: x.replace(microsecond=0))
    return df_latest_prices



@app.callback(
    Output(selected_instruments, 'children'),
    Output('historical-data', 'data'),
    [State(dropdown, 'value')],
    Input(button, 'n_clicks'),
    prevent_initial_call=True
)

def get_data(dropdown,  button):
    prev_time = None
    selected_instruments = dropdown.copy()
    df_instrument_prices = get_historical_data(selected_instruments)

    if df_instrument_prices.shape[0] > 0: # we have some historical data
        prev_time = df_instrument_prices["created_at"].iloc[-1]
        prev_time = int(prev_time.timestamp() * 1000)  # in miliseconds
    df_latest_prices = get_latest_prices(selected_instruments, prev_time)
    df_instrument_prices_ = pd.concat([df_instrument_prices, df_latest_prices], ignore_index=True )
    df_instrument_prices_ = df_instrument_prices_.sort_values(by=["created_at", "instrument_id"])
    df_instrument_prices = df_instrument_prices_.drop_duplicates(subset=["created_at", "instrument_id"], keep='first')
    return selected_instruments, df_instrument_prices.to_dict('records')


@app.callback(
    Output("time-series-chart", "figure"),
    Output('up-to-date-data', 'data'),
    [Input("latest_prices", 'n_intervals')],
    State('historical-data', 'data'),
    State('up-to-date-data', 'data'),
    State(selected_instruments, 'children'),
    prevent_initial_call=True
)
def update_prices(n_intervals, historical_data, up_to_date_data, selected_instruments):
    if n_intervals == 0 or selected_instruments == [] or historical_data == {}: # at the beginning
        raise PreventUpdate
    current_instruments = set(data["instrument_id"] for data in up_to_date_data)
    # user selected another set of instruments and we need to get historical data for them
    if current_instruments != set(selected_instruments):
        up_to_date_data = historical_data.copy()

    df_instrument_prices = pd.DataFrame.from_dict(up_to_date_data)
    df_instrument_prices["created_at"] = pd.to_datetime(df_instrument_prices["created_at"])
    df_latest_prices = get_latest_prices(selected_instruments)

    if df_latest_prices.shape[0] > 0:
        df_instrument_prices_ = pd.concat([df_instrument_prices, df_latest_prices], ignore_index=True )
        df_instrument_prices_ = df_instrument_prices_.sort_values(by=["created_at", "instrument_id"])
        df_instrument_prices = df_instrument_prices_.drop_duplicates(subset=["created_at", "instrument_id"],
                                                                     keep='first')

    fig = go.Figure(layout=go.Layout(xaxis=dict(showgrid=True, title="Time", color="darkred"),
                                     yaxis=dict(showgrid=True, title="Price", color="darkblue")))

    for instrument in selected_instruments:
        df_instrument = df_instrument_prices[df_instrument_prices["instrument_id"] == instrument]
        df_instrument.sort_values(by="created_at")
        fig.add_trace(go.Scatter(x=df_instrument["created_at"], y=df_instrument["price"],
                                 name=TRADING_INSTRUMENTS_WITH_NAMES[instrument]))
    return fig, df_instrument_prices.to_dict('records')


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', debug=False)

