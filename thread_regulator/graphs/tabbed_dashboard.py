from dash import dcc
from dash import html
from dash.dependencies import Output, Input
import dash_bootstrap_components as dbc

import plotly.express as px

from thread_regulator.graphs import app, pg


def get_tab_intro():
    return html.Div([
        html.H1("Dashboard"),
    
        dcc.Graph(id="gi01", figure=pg.get_indicators_requests()),
        html.Br(),
        dcc.Graph(id="gi02", figure=pg.get_gauge_users()),
        html.Br(),
    
        html.Div([dbc.Row([
            dbc.Col([html.Div([pg.get_datatable_statistics()])]),
            dbc.Col([html.Div([pg.get_datatable_settings()])]),
            dbc.Col([html.Div([dcc.Graph(id="g9", figure=pg.get_plot_pie_success_fail_missing())])])
        ], no_gutters=False)]),
    
        html.Br(),    
        dcc.Graph(id="gi03", figure=pg.get_gauge_duration()),
        html.Br(),
        dcc.Graph(id="gi04", figure=pg.get_plot_theoretical_model()),
    ])


def get_tab_duration_analisys():
    cols = ["start", "end", "request_number", "duration", "executions", "success", "failure", "request_result", "user", "users_busy", "block"]
    dropdown_options = [{"label": col, "value": col} for col in cols]

    return html.Div(children=[
        html.H1("Start time / Duration analysis"),
    
        html.Div([dbc.Row([
            dbc.Col([dcc.Dropdown(id="gd_sdf_dropdown_y", options=dropdown_options, value="end")]),
            dbc.Col([dcc.Dropdown(id="gd_sdf_dropdown_x", options=dropdown_options, value="start")])
            ])]),
        html.Br(),
        dcc.Graph(id="gd_sdf"),
        html.Br(),
        dcc.Graph(id="gd01", figure=pg.get_plot_duration_of_each_call()),
        html.Br(),
        dcc.Graph(id="gd02", figure=pg.get_plot_endtime_based_on_starttime()),
        html.Br(),
        dcc.Graph(id="gd03", figure=pg.get_plot_duration_histogram()),
        html.Br(),
        dcc.Graph(id="gd04", figure=pg.get_plot_duration_percentils()),
        html.Br(),
        dcc.Graph(id="gd05", figure=pg.get_plot_endtime_vs_starttime()),
        html.Br(),
        dcc.Graph(id="gd06", figure=pg.get_plot_execution_jitter()),
    ])


@app.callback(Output("gd_sdf", "figure"), [Input("gd_sdf_dropdown_y", "value"), Input("gd_sdf_dropdown_x", "value")])
def update_gd_sdf(prop_y, prop_x):
    fig = px.scatter(pg.get_data_mut(), x=prop_x, y=prop_y, size="duration", color="success", color_discrete_sequence=["#53f677", "#f16940"])
    return fig.update_traces(mode="lines+markers").update_layout(title=f"{prop_y} VS {prop_x}")


def get_tab_resample_analysis():
    return html.Div(children=[
        html.H1("Resample analysis"),
        dcc.Graph(id="gr01", figure=pg.get_plot_resample_executions_start()),
        html.Br(),
        dcc.Graph(id="gr02", figure=pg.get_plot_resample_executions_end()),
    ])


def get_tab_block_analysis():
    return html.Div(children=[
        html.H1("Block time analysis"),
        dcc.Graph(id="gb01", figure=pg.get_plot_block_executions()),
        html.Br(),
        dcc.Graph(id="gb02", figure=pg.get_plot_block_starttime()),
        html.Br(),
        dcc.Graph(id="gb03", figure=pg.get_plot_block_jitter()),
        html.Br(),
        dcc.Graph(id="gb04", figure=pg.get_plot_block_duration()),
        html.Br(),
        dcc.Graph(id="gb05", figure=pg.get_plot_block_scatter())
    ])


def get_layout():
    return dcc.Tabs(children=[
        dcc.Tab(children=[get_tab_intro()], label="Intro"),
        dcc.Tab(children=[get_tab_duration_analisys()], label="Durations"),
        dcc.Tab(children=[get_tab_resample_analysis()], label="Resample"),
        dcc.Tab(children=[get_tab_block_analysis()], label="Block")
    ])
