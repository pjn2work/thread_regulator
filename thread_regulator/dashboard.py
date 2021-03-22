import dash
import dash_table
from dash.dependencies import Output, Input
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import plotly.io as pio
import plotly.express as px
from thread_regulator.graphs import PerformanceGraphs


COLOR_SCHEMES = {
    "dark":  {"stylesheet": dbc.themes.SLATE, "template": "plotly_dark"},
    "white": {"stylesheet": dbc.themes.MINTY, "template": "plotly_white"}
}
COLOR_SCHEME = "dark"
pio.templates.default = COLOR_SCHEMES[COLOR_SCHEME]["template"]

app = dash.Dash("Performance Dashboard", external_stylesheets=[COLOR_SCHEMES[COLOR_SCHEME]["stylesheet"]])


# list of columns we want
pg = PerformanceGraphs()


pg.collect_data("../tests/demo_burst_df.xls")
data_mut = pg._dataframes["sdf"].reset_index()
data_mut["success"] = data_mut["success"].astype(bool)
data_mut["failure"] = data_mut["failure"].astype(bool)


cols = ["start", "end", "request_number", "duration", "executions", "success", "failure", "request_result", "user", "users_busy", "block"]
dropdown_options = [{'label': col, 'value': col} for col in cols]

start_duration_analisys = html.Div(children=[
    html.H1('Start time / Duration analysis'),

    html.Div([dbc.Row([
        dbc.Col([dcc.Dropdown(id='dropdown_y', options=dropdown_options, value='end')]),
        dbc.Col([dcc.Dropdown(id='dropdown_x', options=dropdown_options, value='start')])
        ])]),
    html.Br(),
    dcc.Graph(id='graph_sdf'),
    html.Br(),
    dcc.Graph(id="g20", figure=pg.get_plot_duration_of_each_call()),
    html.Br(),
    dcc.Graph(id="g24", figure=pg.get_plot_endtime_based_on_starttime()),
    html.Br(),
    dcc.Graph(id="g21", figure=pg.get_plot_duration_histogram()),
    html.Br(),
    dcc.Graph(id="g43", figure=pg.get_plot_duration_percentils()),
    html.Br(),
    dcc.Graph(id="g41", figure=pg.get_plot_endtime_vs_starttime()),
    html.Br(),
    dcc.Graph(id="g42", figure=pg.get_plot_execution_jitter()),
])

status_analysis = html.Div(children=[
    html.H1('Status analysis'),
    dcc.Graph(id="g6", figure=pg.get_plot_resample_executions_start()),
    html.Br(),
    dcc.Graph(id="g7", figure=pg.get_plot_resample_executions_end()),
])

block_analysis = html.Div(children=[
    html.H1('Block time analysis'),
    dcc.Graph(id="g50", figure=pg.get_plot_block_executions()),
    html.Br(),
    dcc.Graph(id="g51", figure=pg.get_plot_block_starttime()),
    html.Br(),
    dcc.Graph(id="g52", figure=pg.get_plot_block_jitter()),
    html.Br(),
    dcc.Graph(id="g53", figure=pg.get_plot_block_duration()),
    html.Br(),
    dcc.Graph(id="g54", figure=pg.get_plot_block_scatter())
])


df = pg._dataframes["df_stat"]
if not df.empty:
    df = df[[col for col in df.columns if col not in ["start_time", "end_time"]]]
    df = df.T.reset_index().rename({"index": "Statistics", 0: "values"}, axis=1)


df2 = pg._dataframes["tr_settings"]
if not df2.empty:
    df2 = df2.T.reset_index().rename({"index": "Setup", 0: "values"}, axis=1)


intro = html.Div([
    html.H1('Dashboard'),

    dcc.Graph(id="g13", figure=pg.get_indicators_requests()),
    html.Br(),
    dcc.Graph(id="g10", figure=pg.get_gauge_users()),
    html.Br(),

    html.Div([dbc.Row([
        dbc.Col([html.Div([
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'id': c, 'name': c, 'editable': False} for c in df.columns],
                style_header={'fontWeight': 'bold'},
                style_data_conditional=[{'if': {'column_id': "Statistics"}, 'fontWeight': 'bold'}]
            )
        ])]),
        dbc.Col([html.Div([
            dash_table.DataTable(
                data=df2.to_dict('records'),
                columns=[{'id': c, 'name': c, 'editable': False} for c in df2.columns],
                style_header={'fontWeight': 'bold'},
                style_data_conditional=[{'if': {'column_id': "Setup"}, 'fontWeight': 'bold'}]
            )
        ])]),
        dbc.Col([html.Div([
            dcc.Graph(id="g9", figure=pg.get_plot_pie_success_fail_missing())
        ])])
    ], no_gutters=False)]),

    html.Br(),

    dcc.Graph(id="g23", figure=pg.get_gauge_duration()),
    html.Br(),
    dcc.Graph(id="g8", figure=pg.get_plot_theoretical_model()),

])

app.layout = dcc.Tabs(children=[
    dcc.Tab(children=[intro], label='Intro'),
    dcc.Tab(children=[start_duration_analisys], label="Durations"),
    dcc.Tab(children=[status_analysis], label="Resample"),
    dcc.Tab(children=[block_analysis], label="Block")
])


@app.callback(Output('graph_sdf', 'figure'), [Input('dropdown_y', 'value'), Input('dropdown_x', 'value')])
def update_graph_sdf(prop_y, prop_x):
    fig = px.scatter(data_mut, x=prop_x, y=prop_y, size="duration", color="success", color_discrete_sequence=["#53f677", "#f16940"])
    return fig.update_traces(mode='lines+markers').update_layout(title=f"{prop_y} VS {prop_x}")


if __name__ == '__main__':
    app.run_server(debug=False)
