from thread_regulator import create_regular, create_burst
from thread_regulator.graphs import PerformanceGraphs

from time import sleep


def test_constant_rate():
    notif_count = 0
    notif_time = 0
    call_count = 0
    
    def my_notifier(stats_dict, arg1, **kwargs):
        nonlocal notif_count, notif_time

        assert arg1 == "notify_arg_1"
        assert kwargs["notify_kwarg_2"] == "something"

        if stats_dict["cause"].startswith("finished="):
            assert int(stats_dict["cause"][len("finished="):]) % 5 == 0
            notif_count += 1
        elif stats_dict["cause"].startswith("elapsed="):
            notif_time += 1
            assert int(stats_dict["cause"][len("elapsed="):]) == notif_time
        else:
            raise AssertionError("Cause must be only [finished] or [elapsed]")

    def my_thread_call(user, *args, **kwargs):
        nonlocal call_count

        call_count += 1
        assert len(args) == 2
        assert args[1] == "arg2"
        assert kwargs["arg3"] == "my_val_3"

        sleep(user/50)
        return user == 2

    tr = create_regular(users=3, rps=10.0, duration_sec=3.0, executions=0)
    tr.set_notifier(notify_method=my_notifier,
                    every_sec=1,
                    every_exec=5,
                    notify_method_args=("notify_arg_1", ),
                    notify_kwarg_2="something")
    tr.start(my_thread_call, "arg1", "arg2", arg3="my_val_3", arg4="my_val_4")

    print(tr.get_statistics_as_dict())
    stats = tr.get_statistics()

    # Assert results
    assert 30 <= call_count <= 31
    assert stats.max_requests == 30
    assert stats.ok + stats.ko == call_count
    assert stats.requests_started == call_count
    assert stats.requests_completed == call_count
    assert stats.requests_missing == 0
    assert 3.0 <= stats.execution_seconds <= 3.1
    assert 9.9 <= stats.rps < 10.03
    assert stats.block == 1
    assert round(stats.ts, 4) == 0.1
    assert round(stats.safe_ts, 4) == 0.3
    assert stats.users_busy == 0

    assert notif_time == 2
    assert notif_count == 6

    # Assert PerformanceGraphs Collects
    pg = PerformanceGraphs()
    pg.collect_data(tr)
    pg.save_data("test_regular_df")
    pg.collect_data("test_regular_df")


def test_burst_rate():
    notif_count = 0
    notif_time = 0
    call_count = 0
    
    def my_notifier(stats_dict, arg1, **kwargs):
        nonlocal notif_count, notif_time

        assert arg1 == "notify_arg_1"
        assert kwargs["notify_kwarg_2"] == "something"

        if stats_dict["cause"].startswith("finished="):
            assert int(stats_dict["cause"][len("finished="):]) % 5 == 0
            notif_count += 1
        elif stats_dict["cause"].startswith("elapsed="):
            notif_time += 1
            assert int(stats_dict["cause"][len("elapsed="):]) == notif_time
        else:
            raise AssertionError("Cause must be only [finished] or [elapsed]")

    def my_thread_call(user, *args, **kwargs):
        nonlocal call_count

        call_count += 1
        assert len(args) == 2
        assert args[1] == "arg2"
        assert kwargs["arg3"] == "my_val_3"

        sleep(user/50)
        return user == 2

    tr = create_burst(users=4, rps=20.0, duration_sec=2.0, req=10, dt_sec=0.2, executions=0)
    tr.set_notifier(notify_method=my_notifier,
                    every_sec=1,
                    every_exec=5,
                    notify_method_args=("notify_arg_1", ),
                    notify_kwarg_2="something")
    tr.start(my_thread_call, "arg1", "arg2", arg3="my_val_3", arg4="my_val_4")

    print(tr.get_statistics_as_dict())
    stats = tr.get_statistics()

    # Assert results
    assert 40 <= call_count <= 41
    assert stats.max_requests == 40
    assert stats.ok + stats.ko == call_count
    assert stats.requests_started == call_count
    assert stats.requests_completed == call_count
    assert stats.requests_missing == 0
    assert 1.5 <= stats.execution_seconds <= 1.9
    assert 20.0 < stats.rps < 24.0
    assert stats.block == 4
    assert round(stats.ts, 4) == 0.02
    assert round(stats.safe_ts, 4) == 0.08
    assert stats.users_busy == 0

    assert notif_time == 1
    assert notif_count == 8

    # Assert PerformanceGraphs Collects
    pg = PerformanceGraphs()
    pg.collect_data(tr)
    pg.save_data("test_burst_df")
    pg.collect_data("test_burst_df")


if __name__ == "__main__":
    #test_constant_rate()
    test_burst_rate()