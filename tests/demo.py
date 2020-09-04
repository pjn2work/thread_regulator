from thread_regulator import ThreadRegulator, get_last_thread_regulator, safe_sleep


def demo():
    from random import choice

    def my_notifier(arg1, stats_dict):
        print(arg1, stats_dict)

    def my_thread_call(*args):
        safe_sleep(choice((0.016, 0.020, 0.024)))
        return True

    # x = ThreadRegulator.create_burst(users=4, rps=100, req=100, dt_sec=0.5, duration_sec=None, executions=200)
    ThreadRegulator.create_regular(users=4, rps=10.0, duration_sec=7.0, executions=0). \
        set_notifier(my_notifier, ("notify example", ), every_sec=1, every_exec=15). \
        start(my_thread_call, (0, ))

    last_thread_regulator = get_last_thread_regulator()
    print(last_thread_regulator)

    print("\n", "="*100)
    print("executions started:", last_thread_regulator.get_executions_started())
    print("percentage:", last_thread_regulator.get_percentage_complete(), "\n")

    print("start:", last_thread_regulator.get_start_time())
    print("expect end:", last_thread_regulator.get_defined_end_time())
    print("real end:", last_thread_regulator.get_real_end_time(), "\n")

    print("expect duration:", last_thread_regulator.get_max_duration())
    print("real duration:", last_thread_regulator.get_real_duration())

    return last_thread_regulator


if __name__ == "__main__":
    demo()