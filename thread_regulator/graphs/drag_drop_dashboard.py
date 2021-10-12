from base64 import b64decode
from datetime import datetime
from io import BytesIO

from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State

from thread_regulator.graphs import app, pg
import thread_regulator.graphs.tabbed_dashboard as tb_dash


upload_area = dcc.Upload(
    id="upload-data",
    children=html.Div([
        "Drag and Drop or ",
        html.A("click here to select .xls file")
    ]),
    style={
        "width": "99%",
        "height": "60px",
        "lineHeight": "60px",
        "borderWidth": "1px",
        "borderStyle": "dashed",
        "borderRadius": "5px",
        "textAlign": "center",
        "margin": "10px"
    },
    multiple=False
)

output_graphs_area = html.Div(id="output-data-upload")


app.layout = html.Div([upload_area, output_graphs_area])


def parse_contents(contents, filename, date):
    content_type, content_string = contents.split(",")

    decoded = b64decode(content_string)
    try:
        data_in_bytes = BytesIO(decoded)
        pg.collect_data(data_in_bytes)
    except Exception as e:
        return html.Div([
            html.H1(f"There was an error processing {filename=}"),
            html.H2(str(e))
         ])

    return html.Div([html.H6(f"{filename} {datetime.fromtimestamp(date)}"), tb_dash.get_layout()])


@app.callback(Output("output-data-upload", "children"),
              Input("upload-data", "contents"),
              State("upload-data", "filename"),
              State("upload-data", "last_modified"))
def update_output_after_upload(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        if isinstance(list_of_contents, list):
            children = [parse_contents(c, n, d) for c, n, d in zip(list_of_contents, list_of_names, list_of_dates)]
        else:
            children = [parse_contents(list_of_contents, list_of_names, list_of_dates)]
        return children


def start_dash(**kwargs):
    app.run_server(debug=False, **kwargs)


if __name__ == "__main__":
    start_dash()
