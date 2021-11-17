# ThreadRegulator
Python class that allows to control thread execution in time (requests per second) for both constant rate mode, or burst mode. With a notify option that is called after a specific number of executions or a time delta


### Sample code
```python
from thread_regulator import ThreadRegulator, safe_sleep, create_regular, create_burst
from thread_regulator.graphs import PerformanceGraphs
from random import choice


def demo_constant_rate():
    def my_notifier(stats_dict, arg1, **kwargs):
        print(arg1, stats_dict)

    def my_thread_call(*args, **kwargs):
        safe_sleep(choice((0.1, 0.2, 0.3)))
        return True

    tr = create_regular(users=4, rps=10.0, duration_sec=1.0, executions=15)
    print(tr)
    print("="*100)
    tr.set_notifier(notify_method=my_notifier, every_sec=1, every_exec=8, notify_method_args=("notify_example_arg_1", )).\
        start(my_thread_call, "arg1", "arg2", arg3="my_name", arg4="my_demo")

    return tr


def demo_burst_mode():
    def my_notifier(arg1, stats_dict):
        print(arg1, stats_dict)

    def my_thread_call(*args, **kwargs):
        safe_sleep(choice((0.1, 0.2, 0.3)))
        return True

    tr = create_burst(users=4, rps=10.0, duration_sec=2.0, req=10, dt_sec=0.5, executions=20)
    print(tr)
    print("="*100)

    tr.set_notifier(notify_method=my_notifier, every_sec=1, every_exec=8, notify_method_args=("notify_example_arg_1", )). \
        start(my_thread_call, "arg1", "arg2", arg3="my_name", arg4="my_demo")

    return tr


def show_statistics(tr):
    print("="*100)
    print("Statistics:", tr.get_statistics())
    print(f"Requests start_time jitter:\n{tr.get_execution_dataframe().start_ts.diff().describe()}")
    print(f"Requests call period: {tr.get_executions_call_period()}")
    print(f"Should be executed {tr.get_max_executions()} requests, and {tr.get_executions_started()} were executed, and {tr.get_executions_completed()} completed, and {tr.get_executions_missing()} missing.", )
    print("How many successes over how many requests executed:", tr.get_success_ratio())
    print("How many successes over how many requests should be executed:", tr.get_success_ratio_overall())

    
def save_results(tr, filename):
    pg = PerformanceGraphs()
    # this will save the results on an Excel file (that can be used to plot graphs as explained on last bullet)
    pg.collect_data(tr).save_data(filename)
    

if __name__ == "__main__":
    print("RegularMode")
    show_statistics(demo_constant_rate())

    print("\n\nBurstMode")
    tr = demo_burst_mode()
    show_statistics(tr)

    save_results(tr, "burst_mode_results.xls")
```


### To see the graphical results:
* Run `python -m thread_regulator`
* Open the browser http://127.0.0.1:8050/
* Drag/drop to the browser the .xls file (saved before)


![Counters](https://github.com/pjn2work/thread_regulator/tree/master/sample_images/1intro.jpg "Counters graphs")

![Durations](https://github.com/pjn2work/thread_regulator/tree/master/sample_images/2durations.jpg "Durations graphs")

![Resample](https://github.com/pjn2work/thread_regulator/tree/master/sample_images/3resample.jpg "Resample graphs")