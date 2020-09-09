# ThreadRegulator
Python class that allows to control thread execution in time (requests per second) for both constant rate mode, or burst mode. With a notify option that is called after a specific number of executions or a time delta


```python
from thread_regulator import ThreadRegulator, safe_sleep


def demo_constant_rate():
    from random import choice

    def my_notifier(arg1, stats_dict):
        print(arg1, stats_dict)

    def my_thread_call(*args, **kwargs):
        safe_sleep(choice((0.1, 0.2, 0.3)))
        return True

    tr = ThreadRegulator.create_regular(users=4, rps=10.0, duration_sec=1.0, executions=15)
    print(tr)
    print("="*100)

    tr.set_notifier(my_notifier, ("notify_example_arg_1", ), every_sec=1, every_exec=8).\
        start(my_thread_call, "arg1", "arg2", arg3="my_name", arg4="my_demo")

    print("="*100)
    print(tr.get_statistics())
    print(tr.get_execution_dataframe().start_ts.diff().describe())

    return tr


def demo_burst_mode():
    from random import choice

    def my_notifier(arg1, stats_dict):
        print(arg1, stats_dict)

    def my_thread_call(*args, **kwargs):
        safe_sleep(choice((0.1, 0.2, 0.3)))
        return True

    tr = ThreadRegulator.create_burst(users=4, rps=10.0, duration_sec=2.0, req=10, dt_sec=0.5, executions=20)
    print(tr)
    print("="*100)

    tr.set_notifier(my_notifier, ("notify_example_arg_1", ), every_sec=1, every_exec=8). \
        start(my_thread_call, "arg1", "arg2", arg3="my_name", arg4="my_demo")

    print("="*100)
    print(tr.get_statistics())
    print(tr.get_execution_dataframe().start_ts.diff().describe())

    return tr


if __name__ == "__main__":
    print("RegularMode")
    demo_constant_rate()
    
    print("\n\nBurstMode")
    demo_burst_mode()
```