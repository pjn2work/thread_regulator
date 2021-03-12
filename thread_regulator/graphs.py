from thread_regulator import ThreadRegulator


class PerformanceGraphs:
    agg_secs = [1, 10, 30, 60, 5*60, 10*60, 30*60, 60*60]
    percentiles = [0.01, .05, .25, .50, .75, .90, .95, .99]

    def __init__(self, tr: ThreadRegulator = None):
        assert isinstance(tr, ThreadRegulator), "Must pass a ThreadRegulator class"
        self.tr = tr
        self.agg_sec = None

        # Dataframes
        self.sdf = self.edf = self.bdf = None
        self.srs = self.ers = None
        self.df_sum = self.df_diff = None
        self.df_pt = None

    def _calc_best_groupby_seconds(self):
        agg_sec = self.tr.get_executions_started() / (self.tr.get_real_rps() * 60)

        for v in PerformanceGraphs.agg_secs:
            if agg_sec <= v:
                self.agg_sec = v
                break
        else:
            self.agg_sec = PerformanceGraphs.agg_secs[-1]

    def collect_data(self):
        self._calc_best_groupby_seconds()

        # Dataframe with every single request, indexed by start and end time
        self.sdf = self.tr.get_execution_dataframe(index_on_end=False, group_sec=None)
        self.edf = self.tr.get_execution_dataframe(index_on_end=True, group_sec=None)

        # Dataframe grouped by y sec, indexed by start and end time
        self.srs = self.tr.get_execution_dataframe(index_on_end=False, group_sec=self.agg_sec)
        self.ers = self.tr.get_execution_dataframe(index_on_end=True, group_sec=self.agg_sec)

        # Dataframe grouped by burst block, indexed by start
        self.bdf = self.tr.get_execution_blocks_dataframe()

        # Dataframe with sum of whole df
        self.df_sum = self.sdf[["success", "failure", "executions", "duration"]].sum()
        self.df_sum["max_executions"] = self.tr.get_max_executions()
        self.df_sum["executions_missing"] = self.tr.get_max_executions() - self.df_sum["executions"]

        # Dataframe with the differences between each row
        self.df_diff = self.sdf.reset_index()
        cols = [col for col in self.df_diff.columns if col not in ["request_result"]]
        self.df_diff = self.df_diff[cols].diff()

        # Dataframe describing columns by percentiles
        self.df_pt = self.sdf[["success", "failure", "users_busy", "duration", "thread_safe_period"]].describe(percentiles=PerformanceGraphs.percentiles)

        return self

    # <editor-fold desc=" -= Duration, based on start_time =- ">
    def get_plot_duration_of_each_call(self, figsize=(29, 5), style="-", grid=True, title="Duration of each request in seconds", **kwargs):
        cols = ["ts", "safe_ts", "duration"]
        return self.sdf[cols].plot(ylabel="seconds", legend=True, figsize=figsize, style=style, grid=grid, title=title, **kwargs)

    def get_plot_duration_histogram(self, figsize=(8, 4), bins=10, grid=True, title="Requests duration frequency", **kwargs):
        ax = self.sdf["duration"].plot(kind="hist", figsize=figsize, bins=bins, grid=grid, title=title, **kwargs)
        ax.set_xlabel("seconds")
        for p in ax.patches:
            ax.annotate(str(int(p.get_height())), (p.get_x() + p.get_width()/2, p.get_height() + 0.1), rotation=0, ha="center")
        return ax

    def get_plot_duration_percentils(self, figsize=(29, 5), style="-", grid=True, title="Requests duration", **kwargs):
        return self.sdf["duration"].sort_values().reset_index(drop=True).plot(ylabel="seconds", xlabel="requests", figsize=figsize, style=style, grid=grid, title=title, **kwargs)

    def get_series_duration_percentiles(self, percentiles: list = None):
        if not percentiles or not isinstance(percentiles, list):
            percentiles = PerformanceGraphs.percentiles
        return self.sdf["duration"].describe(percentiles=percentiles)
    # </editor-fold>

    # <editor-fold desc=" -= Start_time vs End_time, Jitter =- ">
    def get_plot_endtime_based_on_starttime(self, figsize=(29, 5), style="-", grid=True, title="End time based on start time", **kwargs):
        return self.sdf["end"].plot(label="end time", ylabel="end time", legend=True, figsize=figsize, style=style, grid=grid, title=title, **kwargs)

    def get_plot_endtime_vs_starttime(self, figsize=(29, 5), style="-", grid=True, title="Start time vs End time", **kwargs):
        cols = ["start_ts", "end_ts"]
        df = self.sdf.reset_index()
        min_start = min(df[cols[0]])
        df[cols[0]] = df[cols[0]] - min_start
        df[cols[1]] = df[cols[1]] - min_start
        return df[cols].plot(xlabel="request", ylabel="seconds", legend=True, figsize=figsize, style=style, grid=grid, title=title, **kwargs)

    def get_plot_execution_jitter(self, figsize=(29, 5), style="-", grid=True, title="Start time jitter", **kwargs):
        return self.df_diff.reset_index().start_ts.plot(ylabel="seconds", xlabel="requests", figsize=figsize, style=style, grid=grid, title=title, **kwargs)

    def get_series_execution_jitter_percentiles(self, percentiles: list = None):
        if not percentiles or not isinstance(percentiles, list):
            percentiles = PerformanceGraphs.percentiles
        return self.df_diff["start_ts"].describe(percentiles=percentiles)
    # </editor-fold>

    # <editor-fold desc=" -= Resample in y sec | executions/success/failure/users_busy =- ">
    def get_plot_resample_executions_start(self, figsize=(29, 5), style=".-", grid=True, title="Requests Started / {} sec", **kwargs):
        cols = ["executions", "users_busy", "success", "failure"]
        if len(self.srs) > 1:
            return self.srs[cols].plot(ylabel="requests", legend=True, figsize=figsize, style=style, grid=grid, title=title.format(self.agg_sec), **kwargs)

    def get_plot_resample_executions_end(self, figsize=(29, 5), style=".-", grid=True, title="Requests Ended / {} sec", **kwargs):
        cols = ["executions", "users_busy", "success", "failure"]
        if len(self.ers) > 1:
            return self.ers[cols].plot(ylabel="requests", legend=True, figsize=figsize, style=style, grid=grid, title=title.format(self.agg_sec), **kwargs)

    def get_plot_pie_success_fail_missing(self, figsize=(7, 6), title="Requests", **kwargs):
        cols = ["executions_missing", "failure", "success"]
        return self.df_sum[cols].plot.pie(legend=True, shadow=True, startangle=90, explode=(0.05, 0.1, 0.05), autopct='%1.1f%%', ylabel="", figsize=figsize, title=title, **kwargs)
    # </editor-fold>

    # <editor-fold desc=" -= Burst Blocks =- ">
    def get_dataframe_block_percentiles(self, percentiles: list = None):
        if not percentiles or not isinstance(percentiles, list):
            percentiles = PerformanceGraphs.percentiles
        return self.bdf.describe(percentiles=percentiles)

    def get_plot_block_starttime(self, figsize=(29, 5), style=".-", title="Block start time", **kwargs):
        return self.bdf["start"].plot(grid=True, ylabel="start time", figsize=figsize, style=style, title=title, **kwargs)

    def get_plot_block_jitter(self, figsize=(29, 5), style=".-", title="Block start time Jitter", **kwargs):
        return self.bdf["start"].diff().dt.total_seconds().plot(ylabel="seconds", grid=True, figsize=figsize, style=style, title=title, **kwargs)

    def get_plot_block_duration(self, figsize=(29, 4), style=".-", title="Blocks duration", **kwargs):
        return self.bdf["block_duration_sec"].plot(ylabel="duration (sec)", grid=True, figsize=figsize, style=style, title=title, **kwargs)

    def get_plot_block_executions(self, figsize=(29, 4), style=".-", title="Executions per block", **kwargs):
        cols = ["executions", "is_above_ts", "success", "failure", "users_busy"]
        return self.bdf[cols].plot(ylabel="sum()", grid=True, figsize=figsize, style=style, title=title, **kwargs)
    # </editor-fold>
