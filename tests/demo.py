from thread_regulator import ThreadRegulator, create_regular, create_burst
from thread_regulator.graphs import PerformanceGraphs
from random import choice
from time import sleep


def demo_constant_rate():
    def my_notifier(stats_dict, arg1, **kwargs):
        print("NotifierMethod", arg1, kwargs, stats_dict)

    def my_thread_call(user, *args, **kwargs):
        c = choice((0.1, 0.2, 0.3))
        sleep(c)
        print(f"ExecutionUser{user} for {c} seconds", args, kwargs)
        return c == 0.1

    tr = create_regular(users=2, rps=10.0, duration_sec=3.0, executions=0)
    print(tr)
    print("="*100)
    tr.set_notifier(notify_method=my_notifier,
                    every_sec=1,
                    every_exec=8,
                    notify_method_args=("notify_arg_1", ),
                    notify_kwarg_2="someting")
    tr.start(my_thread_call, "arg1", "arg2", arg3="my_val_3", arg4="my_val_4")

    pg = PerformanceGraphs()
    pg.collect_data(tr)
    pg.save_data("demo_regular_df")
    pg.collect_data("demo_regular_df")

    return tr


def demo_burst_mode():
    def my_notifier(stats_dict, arg1, **kwargs):
        print("NotifierMethod", arg1, kwargs, stats_dict)

    def my_thread_call(user, *args, **kwargs):
        #print(f"ExecutionUser{user}", args, kwargs)
        c = choice((0.1, 0.2, 0.3))
        sleep(c)
        return c == 0.1

    tr = create_burst(users=4, rps=20.0, duration_sec=4.0, req=10, dt_sec=0.2, executions=0)
    print(tr)
    print("="*100)

    tr.set_notifier(notify_method=my_notifier,
                    every_sec=1,
                    every_exec=20,
                    notify_method_args=("notify_arg_1", ),
                    notify_kwarg_2=True)
    tr.start(my_thread_call, "arg1", "arg2", arg3="my_val_3", arg4="my_val_4")

    pg = PerformanceGraphs()
    pg.collect_data(tr)
    pg.save_data("demo_burst_df")
    pg.collect_data("demo_burst_df")

    return tr


def show_statistics(tr: ThreadRegulator):
    print("="*100)
    print("Statistics dict:", tr.get_statistics_as_dict())
    print("Statistics dataclass:", tr.get_statistics())
    print(f"Requests start_time jitter:\n{tr.get_execution_dataframe().start_ts.diff().describe()}")
    print(f"Requests call period: {tr.get_executions_call_period()}")
    print(f"Should be executed {tr.get_max_executions()} requests, and {tr.get_executions_started()} were executed, and {tr.get_executions_completed()} completed, and {tr.get_executions_missing()} missing.", )
    print("How many successes over how many requests executed:", tr.get_success_ratio())
    print("How many successes over how many requests should be executed:", tr.get_success_ratio_overall())


if __name__ == "__main__":
    print("RegularMode")
    show_statistics(demo_constant_rate())

    print("\n\nBurstMode")
    show_statistics(demo_burst_mode())
