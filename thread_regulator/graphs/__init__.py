import dash
import dash_bootstrap_components as dbc

import plotly.io as pio

from thread_regulator.graphs.performance_graphs import PerformanceGraphs


COLOR_SCHEMES = {
    "dark":  {"stylesheet": dbc.themes.SLATE, "template": "plotly_dark"},
    "white": {"stylesheet": dbc.themes.MINTY, "template": "plotly_white"}
}
COLOR_SCHEME = "dark"
pio.templates.default = COLOR_SCHEMES[COLOR_SCHEME]["template"]


app = dash.Dash("Performance Dashboard", external_stylesheets=[COLOR_SCHEMES[COLOR_SCHEME]["stylesheet"]])
pg = PerformanceGraphs()
