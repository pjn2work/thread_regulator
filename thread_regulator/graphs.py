from os import path
from thread_regulator import ThreadRegulator, pd
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc


# https://www.w3.org/TR/css-color-3/#svg-color


def include_percentils(*pcts) -> list:
    p = list(PerformanceGraphs.percentiles)
    for pct in pcts:
        if pct not in p:
            p.append(pct)
    return p


class PerformanceGraphs:
    agg_secs = [1, 10, 30, 60, 5*60, 10*60, 30*60, 60*60]
    percentiles = [0.01, .05, 0.1, .25, .50, .75, .90, .95, .99]

    def __init__(self):
        # Dataframes
        self._dataframes = {"tr_settings": pd.DataFrame(), "df_stat": pd.DataFrame(), "df_pt": pd.DataFrame(),
                            "sdf": pd.DataFrame(), "edf": pd.DataFrame(), "bdf": pd.DataFrame(),
                            "srs": pd.DataFrame(), "ers": pd.DataFrame(), "df_diff": pd.DataFrame(),
                            "df_tm": pd.DataFrame()}

    # <editor-fold desc=" -= Save or Collect data =- ">
    def save_data(self, filename: str = None):
        assert isinstance(filename, str), f"must pass a valid filename string"
        if not filename.endswith(".xlsx") and not filename.endswith(".xls"):
            filename += ".xls"

        xls_writer = pd.ExcelWriter(filename, engine='xlsxwriter', datetime_format='yyyy-mm-dd hh:mm:ss.000')

        for df_name in self._dataframes:
            self._dataframes[df_name].to_excel(xls_writer, index=True, header=True, sheet_name=df_name)

        xls_writer.save()

        return self

    def collect_data(self, from_tr_or_file):
        if isinstance(from_tr_or_file, ThreadRegulator):
            return self._collect_data_from_threadregulator(from_tr_or_file)
        if isinstance(from_tr_or_file, str):
            return self._collect_data_from_files(from_tr_or_file)
        raise Exception(f"Must pass a ThreadRegulator or a filename to where the dataframes were stored")

    def _collect_data_from_files(self, filename: str):
        if not filename.endswith(".xlsx") and not filename.endswith(".xls"):
            filename += ".xls"
        assert path.isfile(filename), f"{filename!r} does not exist"

        for df_name in self._dataframes:
            self._dataframes[df_name] = pd.read_excel(filename, header=0, index_col=0, sheet_name=df_name)

        return self

    def _calc_best_groupby_seconds(self, tr):
        agg_sec = tr.get_executions_started() / (tr.get_real_rps() * 60)

        for v in PerformanceGraphs.agg_secs:
            if agg_sec <= v:
                return v
        return PerformanceGraphs.agg_secs[-1]

    def _collect_data_from_threadregulator(self, tr: ThreadRegulator):
        assert tr.get_executions_started() > 1, f"ThreadRegulator didn't ran or produce more than 1 execution"

        # Calculate the best value in secs to aggregate the burst graphs
        agg_sec = self._calc_best_groupby_seconds(tr)

        # Dataframe with setup settings for ThreadRegulator
        self._dataframes["tr_settings"] = pd.json_normalize(tr.get_run_param(), sep='_')

        # Theoretical Model Dataframe
        self._dataframes["df_tm"] = tr.get_theoretical_model_dataframe()

        # Dataframe with every single request, indexed by start and end time
        self._dataframes["sdf"] = sdf = tr.get_execution_dataframe(index_on_end=False, group_sec=None)
        self._dataframes["edf"] = tr.get_execution_dataframe(index_on_end=True, group_sec=None)

        # Dataframe grouped by y sec, indexed by start and end time
        self._dataframes["srs"] = tr.get_execution_dataframe(index_on_end=False, group_sec=agg_sec)
        self._dataframes["ers"] = tr.get_execution_dataframe(index_on_end=True, group_sec=agg_sec)

        # Dataframe grouped by burst block, indexed by start
        self._dataframes["bdf"] = tr.get_execution_blocks_dataframe()

        # Dataframe with the differences between each row
        self._dataframes["df_diff"] = df_diff = sdf.reset_index()
        cols = ["start_ts", "end_ts", "duration", "thread_safe_period"]
        self._dataframes["df_diff"] = df_diff[cols].diff().iloc[1:]

        # Dataframe describing columns by percentiles
        self._dataframes["df_pt"] = sdf[["success", "failure", "users_busy", "duration", "thread_safe_period"]].describe(percentiles=PerformanceGraphs.percentiles)

        # Dataframe with the overall statistics
        self._dataframes["df_stat"] = tr.get_statistics_dataframe()
        self._dataframes["df_stat"]["agg_sec"] = agg_sec

        return self
    # </editor-fold>

    def _gf_settings(self, col):
        return self._dataframes["tr_settings"].loc[0, col]

    def _gf_statistics(self, col):
        return self._dataframes["df_stat"].loc[0, col]

    def _gf_percentiles(self, row, col):
        return self._dataframes["df_pt"].loc[row, col]

    # <editor-fold desc=" -= Gauges =- ">
    def get_gauge_users(self, **kwargs):
        if self._dataframes["df_stat"].empty or self._dataframes["tr_settings"].empty or self._dataframes["df_pt"].empty:
            return None

        real_rps = self._gf_statistics("rps")
        defined_rps = self._gf_settings("rps")

        elapsed_sec = self._gf_statistics("elapsed_seconds")

        total_users = self._gf_settings("users")
        users_busy = self._gf_percentiles("max", "users_busy")
        median_users_busy = round(self._gf_percentiles("50%", "users_busy"), 1)

        fig = go.Figure()

        fig.add_trace(go.Indicator(mode="gauge+number+delta", value=real_rps, title="RPS", domain={"row": 0, "column": 0},
                                   delta={'reference': defined_rps},
                                   gauge={'axis': {'range': [0, defined_rps]}}))

        fig.add_trace(go.Indicator(mode="number", value=elapsed_sec, title="Elapsed seconds", domain={"row": 0, "column": 1}))

        fig.add_trace(go.Indicator(mode="gauge+number", value=users_busy, title={'text': "Max users busy"}, domain={"row": 0, "column": 2},
                                   gauge={'axis': {'range': [0, total_users]},
                                          'threshold': {'line': {'color': "orange", 'width': 4}, 'thickness': 0.75, 'value': median_users_busy}}))

        return fig.update_layout(grid={'rows': 1, 'columns': 3, 'pattern': "independent"}, **kwargs)

    def get_gauge_duration(self, **kwargs):
        if self._dataframes["sdf"].empty:
            return None

        fig = go.Figure()

        for col, dfilter in enumerate(['executions', 'success', 'failure']):
            row_filter = self._dataframes["sdf"][dfilter] == 1
            data = self._dataframes["sdf"][row_filter].duration
            if data.empty:
                continue
            data = data.describe(percentiles=include_percentils(0.50, 0.90))

            value = round(data.loc["90%"], 3)
            median = round(data.loc["50%"], 3)

            total = self._gf_percentiles("max", "duration")
            ts = self._gf_settings("block_ts")
            safe_ts = self._gf_settings("user_threadsafe_ts")
            total = max(total, safe_ts)

            if value <= ts:
                color = "gold"
            elif value <= safe_ts:
                color = "green"
            else:
                color = "red"

            fig.add_trace(
                go.Indicator(mode="gauge+number+delta",
                             title={'text': f"Duration for 90% {dfilter}"},
                             value=value,
                             delta={'reference': safe_ts},
                             gauge={'axis': {'range': [0, total]},
                                    'bar': {'color': color},
                                    'threshold': {'line': {'color': "orange", 'width': 4}, 'thickness': 0.75, 'value': median},
                                    'steps': [
                                        {'range': [0, ts], 'color': 'lightyellow'},
                                        {'range': [ts, safe_ts], 'color': 'lightgreen'},
                                        {'range': [safe_ts, total], 'color': 'tomato'}]},
                             domain={"row": 0, "column": col}))

        return fig.update_layout(grid={'rows': 1, 'columns': 3, 'pattern': "independent"}, **kwargs)

    def get_indicators_requests(self):
        if self._dataframes["df_stat"].empty:
            return None

        success_ratio = round(float(self._gf_statistics("success_ratio")) * 100, 2)
        overall_success_ratio = round(float(self._gf_statistics("overall_success_ratio")) * 100, 2)

        total = self._gf_statistics("max_requests")
        started = self._gf_statistics("requests_started")
        completed = self._gf_statistics("requests_completed")
        missed = self._gf_statistics("requests_missing")
        success = self._gf_statistics("ok")
        failure = self._gf_statistics("ko")

        fig = go.Figure()

        fig.add_trace(go.Indicator(mode="gauge+number+delta", value=completed, title={'text': "Completed requests"}, domain={"row": 0, "column": 0},
                                   delta={'reference': started},
                                   gauge={'axis': {'range': [0, total]}, 'bar': {'color': "green"},
                                          'threshold': {'line': {'color': "orange", 'width': 4}, 'thickness': 0.75, 'value': started}}))

        fig.add_trace(go.Indicator(mode="gauge+number", value=success_ratio, title={'text': "Success ratio"}, domain={"row": 0, "column": 2},
                                   number={'suffix': "%"},
                                   gauge={'axis': {'range': [0, 100]},
                                          'threshold': {'line': {'color': "orange", 'width': 4}, 'thickness': 0.75, 'value': overall_success_ratio}}))

        fig.add_trace(go.Indicator(mode="number", value=completed, title="Completed requests", domain={"row": 0, "column": 1}))
        fig.add_trace(go.Indicator(mode="number", value=success, title="Success requests", domain={"row": 0, "column": 3}))
        fig.add_trace(go.Indicator(mode="number", value=failure, title="Failed requests", domain={"row": 0, "column": 4}))
        fig.add_trace(go.Indicator(mode="number", value=missed, title="Missing requests", domain={"row": 0, "column": 5}))

        return fig.update_layout(grid={'rows': 1, 'columns': 6, 'pattern': "independent"})
    # </editor-fold>

    # <editor-fold desc=" -= Duration, based on start_time =- ">
    def get_plot_theoretical_model(self, title="Theoretical Model", **kwargs):
        if self._dataframes["df_tm"].empty:
            return None
        d2p = self._dataframes["df_tm"]

        fig = px.bar(d2p, title=title, log_y=True, **kwargs)

        return fig.update_layout(xaxis_title="Start time (sec)", yaxis_title="User")

    def get_plot_duration_of_each_call(self, title="Duration of each request (in sec)", **kwargs):
        if self._dataframes["sdf"].empty:
            return None
        cols = ["ts", "safe_ts", "duration"]
        d2p = self._dataframes["sdf"][cols]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="Start time", yaxis_title="Duration (in sec)")

    def get_plot_duration_histogram(self, bins=10, **kwargs):
        if self._dataframes["sdf"].empty:
            return None

        fig = go.Figure()

        for dfilter in ['executions', 'failure', 'success']:
            row_filter = self._dataframes["sdf"][dfilter] == 1
            d2p = self._dataframes["sdf"][row_filter].duration
            if d2p.empty:
                continue

            fig.add_trace(go.Histogram(x=d2p, histfunc="count", nbinsx=bins, name=dfilter))

        return fig.update_layout(xaxis_title="Duration (in sec)", yaxis_title="# Requests", **kwargs)

    def get_plot_duration_percentils(self, title="Requests duration", **kwargs):
        if self._dataframes["sdf"].empty:
            return None

        d2p = self._dataframes["sdf"].duration.sort_values().reset_index(drop=True)

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="Requests", yaxis_title="Seconds")

    def get_series_duration_percentiles(self):
        return self._dataframes["df_pt"]["duration"]
    # </editor-fold>

    # <editor-fold desc=" -= Start_time vs End_time, Jitter =- ">
    def get_plot_endtime_based_on_starttime(self, title="End time based on start time", **kwargs):
        if self._dataframes["sdf"].empty:
            return None

        d2p = self._dataframes["sdf"]["end"]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="Start time", yaxis_title="End time")

    def get_plot_endtime_vs_starttime(self, title="Start time vs End time", **kwargs):
        if self._dataframes["sdf"].empty:
            return None
        cols = ["start_ts", "end_ts"]
        df = self._dataframes["sdf"].reset_index()
        min_start = min(df[cols[0]])
        df[cols[0]] = df[cols[0]] - min_start
        df[cols[1]] = df[cols[1]] - min_start
        d2p = df[cols]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="Request", yaxis_title="Seconds")

    def get_plot_execution_jitter(self, show_ts=False, show_safe_ts=False, title="Start time jitter", **kwargs):
        if self._dataframes["df_diff"].empty:
            return None
        cols = ["start_ts"]
        d2p = self._dataframes["df_diff"].reset_index()[cols]
        if show_ts:
            d2p["ts"] = self._dataframes["sdf"].ts.max()
        if show_safe_ts:
            d2p["safe_ts"] = self._dataframes["sdf"].safe_ts.max()

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="Request", yaxis_title="Seconds")

    def get_series_execution_jitter_percentiles(self, percentiles: list = None):
        if not percentiles or not isinstance(percentiles, list):
            percentiles = PerformanceGraphs.percentiles

        return self._dataframes["df_diff"]["start_ts"].describe(percentiles=percentiles)
    # </editor-fold>

    # <editor-fold desc=" -= Resample in y sec | executions/success/failure/users_busy =- ">
    def _get_plot_resample_executions(self, df, title="", xtitle="", **kwargs):
        if len(df) < 2:
            return None
        cols = ["executions", "failure", "success", "users_busy"]
        d2p = df[cols]
        resample_period = self._dataframes["df_stat"]["agg_sec"].max()

        fig = px.line(d2p, title=title.format(resample_period), **kwargs)

        return fig.update_layout(xaxis_title=xtitle, yaxis_title="# Requests")

    def get_plot_resample_executions_start(self, title="Requests Started / {} sec", **kwargs):
        return self._get_plot_resample_executions(self._dataframes["srs"], title=title, xtitle="Start time", **kwargs)

    def get_plot_resample_executions_end(self, title="Requests Ended / {} sec", **kwargs):
        return self._get_plot_resample_executions(self._dataframes["ers"], title=title, xtitle="End time", **kwargs)

    def get_plot_pie_success_fail_missing(self, title="Requests", hole=.5, **kwargs):
        if self._dataframes["df_stat"].empty:
            return None

        colors = {"ok": "lightgreen", "ko": "red", "requests_missing": "gray"}
        d2p = self._dataframes["df_stat"][colors.keys()]
        d2p = d2p.sum().reset_index().rename({"index": "name", 0: "value"}, axis=1)

        return px.pie(d2p, names="name", values="value", title=title, color="name", color_discrete_map=colors, hole=hole, **kwargs).update_traces(textposition='inside')
    # </editor-fold>

    # <editor-fold desc=" -= Burst Blocks =- ">
    def get_dataframe_block_percentiles(self, percentiles: list = None):
        if not percentiles or not isinstance(percentiles, list):
            percentiles = PerformanceGraphs.percentiles

        return self._dataframes["bdf"].describe(percentiles=percentiles)

    def get_plot_block_starttime(self, title="Block start time", **kwargs):
        if self._dataframes["bdf"].empty:
            return None

        d2p = self._dataframes["bdf"]["start"]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="# Block", yaxis_title="Block start time")

    def get_plot_block_jitter(self, title="Block start time Jitter", **kwargs):
        if len(self._dataframes["bdf"]) < 2:
            return None

        d2p = self._dataframes["bdf"]["start"].diff().iloc[1:].dt.total_seconds()
        if d2p.empty:
            return None

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="# Block", yaxis_title="Seconds")

    def get_plot_block_duration(self, title="Blocks duration", **kwargs):
        if self._dataframes["bdf"].empty:
            return None

        d2p = self._dataframes["bdf"]["block_duration_sec"]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="# Block", yaxis_title="Duration (sec)")

    def get_plot_block_executions(self, title="Executions per block", **kwargs):
        if self._dataframes["bdf"].empty:
            return None

        cols = ["executions", "failure", "success", "users_busy", "above_safe_ts"]
        d2p = self._dataframes["bdf"][cols]

        return px.line(d2p, title=title, **kwargs).update_layout(xaxis_title="# Block", yaxis_title="Sum()")

    def get_plot_block_scatter(self, title="Block success/duration/users_busy", **kwargs):
        d2p = self._dataframes["bdf"]

        fig = px.scatter(d2p, x="start", y="success", size="block_duration_sec", color="users_busy", title=title, **kwargs)

        return fig.update_traces(mode='lines+markers')
    # </editor-fold>
