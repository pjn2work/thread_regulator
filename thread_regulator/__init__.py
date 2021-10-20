from threading import Thread, Lock
from time import time, sleep
from datetime import datetime
from collections import Counter
from math import ceil

import pandas as pd


__version__ = "0.2.3"


def frange(start, stop, step, precision=7):
    i = start
    while i < stop:
        yield i
        i = round(i + step, precision)


def create_regular(users: int, rps: float, duration_sec: float, executions: int):
    return ThreadRegulator(users, rps, None, None, duration_sec, executions)


def create_burst(users: int, rps: float, req: int, dt_sec: float, duration_sec: float, executions: int):
    return ThreadRegulator(users, rps, req, dt_sec, duration_sec, executions)


class ThreadRegulator:

    def __init__(self, users: int, rps: float, req: int, dt_sec: float, duration_sec: float, executions: int):
        self.run_param = {"users": users,
                          "rps": rps,
                          "duration_sec": duration_sec,
                          "executions": executions,
                          "block": dict(),
                          "mode": None}

        # validate users and rps
        assert 1 <= users <= 256, "'users' must be between 1..256"
        assert rps and rps > 0.0, "'rps' must be > 0.0"

        # run deadline, either from number of executions or time, or both: whatever finishes first
        assert duration_sec or executions, "Must have a deadline. At least one of 'executions' or 'duration_sec' must be set."
        if duration_sec:
            assert duration_sec > 0.0, "'duration_sec' must be > 0.0"
        if executions:
            assert executions > 0, "'executions' must be > 0"

        # for burst or regular mode
        if req and dt_sec:
            assert req >= 1, "'req' must be >= 1"
            assert dt_sec > 0.0, "'dt_sec' must be > 0.0"
            assert req/dt_sec >= rps, f"Can't reach rps={rps} with (req={req}, dt={dt_sec}). Consider changing 'rps' or 'req' or 'dt_sec' so that req/dt_sec > rps"
            self.run_param["mode"] = "burst"
        elif not req and not dt_sec:
            self.run_param["mode"] = "regular"
            if executions:
                req = executions
                dt_sec = executions / rps
            else:
                req = ceil(rps * duration_sec)
                dt_sec = req / rps
        else:
            assert req, f"For burst mode you need to specify 'req' and 'dt_sec', you're missing 'req'. For regular mode, both must be equal to None"
            assert dt_sec, f"For burst mode you need to specify 'req' and 'dt_sec', you're missing 'dt_sec'. For regular mode, both must be equal to None"

        # define burst-block
        block = self.run_param["block"]
        block["req"] = req                          # number of requests per burst-block
        block["busy"] = dt_sec                      # busy duration of a burst-block
        block["rps"] = req / dt_sec                 # requests-per-second on each burst-block
        block["ts"] = dt_sec / req                  # duration of a single request on a burst-block (timeslot)
        block["duration"] = d = req / rps           # total duration of the burst_block( busy + idle )
        block["idle"] = d - dt_sec                  # idle duration of a burst-block, waiting for starting another block

        # safe period that a thread can be busy without compromising other threads to keep the rps
        self.run_param["user_threadsafe_ts"] = block["ts"] * users

        # total requests that should be executed in theory
        self.run_param["max_executions"] = self._calc_max_executions_based_on_duration()

        # create control plane for running threads
        self.run_control = {
            "thread_list": list(),
            "running": False,
            "method": None,
            "args": None,
            "kwargs": None,

            "busy_workers": set(),
            "global_executions": 0,
            "global_start_time": None,
            "global_end_time":  None,
            "global_last_run_timestamp": None,
            "global_real_end_time": None,
            "global_ok": 0,
            "global_ko": 0,

            "block": {
                "id": 0,
                "requests_left": 0,
                "next_run": None,
                "ends_at": None,
                "busy_until": None
            }
        }

        # to call upon evey Y sec to notify progress
        self.notifier = {"method": None, "args": None, "every_exec": 0, "every_sec": 0}

        # execution list with all entrys of:
        #    (time_request_started, time_request_ended, request_success, user_id, block_id, request_result)
        self.execution_log = list()

    def _calc_max_executions_based_on_duration(self):
        # if no duration set then the maximum executions are the ones defined
        duration = self.get_defined_duration()
        if duration == 0.0:
            return self.get_defined_executions()

        # if not burst mode then executions = rps * duration, which is the whole burst block
        if self.is_mode_regular():
            return self.get_defined_burst_requests()

        # (How many blocks can be sent during * how many requests each block sends) + (remaining duration * block rps)
        total_bursts_blocks = int(duration / self.get_defined_burst_duration())
        last_burst_requests_duration = min(self.get_defined_burst_busy(), duration - total_bursts_blocks * self.get_defined_burst_duration())
        total_executions = int((total_bursts_blocks * self.get_defined_burst_requests()) + (last_burst_requests_duration * self.get_defined_burst_rps()))

        # if defined how many executions then return min(max executions calculated, defined executions)
        if self.get_defined_executions():
            return int(min(total_executions, self.get_defined_executions()))

        return total_executions
    # <editor-fold desc=" -= class common methods =- ">

    def set_notifier(self, notify_method=print, every_sec=5, every_exec=0, notify_method_args=tuple(), **notify_method_kwargs):
        """
        :param notify_method: The method to be called
        :param every_sec: Every x seconds the notify_method will be called
        :param every_exec: Every x requests started the notify_method will be called
        :param notify_method_args: Methods args that are sent back along with statistics
        :param notify_method_kwargs: Methods kwargs that are sent back along with statistics
        :return: will call the notify_method(stats_dict, *args, **kwargs)
            {executions_started, elapsed_seconds, percentage_complete, success_ratio, ok, ko}
        """
        assert callable(notify_method), "'notify_method' must be a valid callable method with args"
        assert isinstance(notify_method_args, (tuple, list)), "'notify_method_args' must be a tuple or list"
        assert every_exec or every_sec, "Must define at least one (can be both) of 'every_exec' and/or 'every_sec'"
        if every_exec:
            assert every_exec >= 1, "'every_exec' must be >= 1"
        if every_sec:
            assert every_sec >= 1, "'every_sec' must be >= 1"

        self.notifier["method"] = notify_method
        self.notifier["every_sec"] = every_sec
        self.notifier["every_exec"] = every_exec
        self.notifier["args"] = notify_method_args
        self.notifier["kwargs"] = notify_method_kwargs

        return self

    def get_run_param(self) -> dict:
        return dict(self.run_param)

    def is_mode_regular(self) -> bool:
        return self.run_param["mode"] == "regular"

    def is_mode_burst(self) -> bool:
        return self.run_param["mode"] == "burst"

    def get_user_threadsafe_period(self) -> float:
        return self.run_param["user_threadsafe_ts"]

    def get_defined_users(self) -> int:
        return self.run_param["users"]

    def get_defined_rps(self) -> float:
        return self.run_param["rps"]

    def get_defined_duration(self) -> float:
        return self.run_param["duration_sec"]

    def get_defined_executions(self) -> int:
        return self.run_param["executions"]

    def get_defined_burst_requests(self) -> int:
        return self.run_param["block"]["req"]

    def get_defined_burst_rps(self) -> float:
        return self.run_param["block"]["rps"]

    def get_defined_burst_ts(self) -> float:
        return self.run_param["block"]["ts"]

    def get_defined_burst_duration(self) -> float:
        return self.run_param["block"]["duration"]

    def get_defined_burst_busy(self) -> float:
        return self.run_param["block"]["busy"]

    def get_defined_burst_idle(self) -> float:
        return self.run_param["block"]["idle"]

    def get_max_executions(self):
        return self.run_param["max_executions"]

    def get_execution_list(self) -> list:
        return self.execution_log

    def get_execution_counter_of_responses(self) -> dict:
        return dict(Counter([row[-1] for row in self.execution_log]).items())

    def get_execution_dataframe(self, index_on_end: bool = False, group_sec: int = None) -> pd.DataFrame:
        df = pd.DataFrame(self.get_execution_list(), columns=("start_ts", "end_ts", "success", "user", "block", "users_busy", "request_result"))

        # to set the executions to start on second x.000
        ms_diff = df.start_ts.min()
        ms_diff = ms_diff - int(ms_diff)

        # calc duration above TSP to be more or less the time each user has before compromising number of threads
        df["duration"] = df["end_ts"] - df["start_ts"]
        df["thread_safe_period"] = df["duration"] - self.get_user_threadsafe_period()

        # convert bool to int
        df["success"] = df["success"].astype(int)
        df["failure"] = ~df["success"] + 2
        df["executions"] = 1

        # set start and end timestamps in datetime format
        df["start"] = df["start_ts"].apply(lambda x: datetime.fromtimestamp(x -ms_diff))
        df["end"] = df["end_ts"].apply(lambda x: datetime.fromtimestamp(x -ms_diff))

        # add request sequential order number of execution
        df = df.set_index("start_ts").sort_index().reset_index()
        df["request_number"] = df.index + 1

        # set index on start or end
        if index_on_end:
            df.set_index("end", inplace=True)
            include_field = "start"
        else:
            df.set_index("start", inplace=True)
            include_field = "end"

        # set static values
        df["mean_rps"] = self.get_real_rps()
        df["ts"] = self.get_defined_burst_ts()
        df["safe_ts"] = self.get_user_threadsafe_period()

        # convert to an average df by grouping results in seconds
        if group_sec:
            include_fields = {"start": "min", "end": "max"}
            filter_agg = {"success": "sum", "failure": "sum", "executions": "sum", "duration": "median", "users_busy": "max", "request_number": "min", "thread_safe_period": "max", "block": "median", "ts": "max", "safe_ts": "max", include_field: include_fields[include_field]}
            df = df[filter_agg.keys()].resample(f"{group_sec}s").agg(filter_agg)
            df.rename(columns={"duration": "duration_med"}, inplace = True)

        return df.sort_index()

    def get_execution_blocks_dataframe(self) -> pd.DataFrame:
        df = self.get_execution_dataframe()

        # check for executions that went above the thread safe period
        df["above_safe_ts"] = df["thread_safe_period"] > 0.0
        df["above_safe_ts"] = df["above_safe_ts"].astype(int)

        # column selection, grouping by block number
        filter_agg = {"start": "min", "end": "max", "success": "sum", "failure": "sum", "executions": "sum", "duration": "median", "above_safe_ts": "sum", "users_busy": "max", "request_number": "min"}
        filter_columns = ["block"] + list(filter_agg.keys())
        gdf = df.reset_index()[filter_columns]
        gdf = gdf.groupby("block").agg(filter_agg)
        gdf.rename(columns={"duration": "duration_med"}, inplace = True)

        # calculate block duration
        gdf["block_duration"] = gdf["end"] - gdf["start"]
        gdf["block_duration_sec"] = gdf["block_duration"].dt.total_seconds()
        gdf["block_duration"] = gdf["block_duration"].apply(lambda s: str(s)[7:])

        return gdf

    def get_statistics_dataframe(self) -> pd.DataFrame:
        stat = {k: [v] for k, v in self.get_statistics().items()}
        return pd.DataFrame.from_dict(stat, orient="columns")

    def get_theoretical_model_dataframe(self):
        if self.is_mode_regular():
            time_window = min(1.0, self.get_defined_burst_duration()) + self.get_defined_burst_ts()
        else:
            time_window = max(1.0, self.get_defined_burst_duration()) + self.get_defined_burst_ts()

        # build the execution timeline
        df = pd.DataFrame(columns=["user"])
        user = 0
        for t_sec in frange(0.0, time_window, self.get_defined_burst_ts(), precision=6):
            ts = round(t_sec % self.get_defined_burst_duration(), 6)

            if ts < self.get_defined_burst_busy():
                ruser = user + 1
                user = (user + 1) % self.get_defined_users()
            else:
                ruser = 0

            df.loc[t_sec] = ruser

        return df

    # </editor-fold>

    # <editor-fold desc=" -= control plane =- ">

    def is_running(self) -> bool:
        return self.run_control["running"]

    def get_percentage_complete(self) -> float:
        tot_exec = round(100 * self.get_executions_started() / self.get_defined_executions(), 2) if self.get_defined_executions() else 0.0
        tot_time = round(100 * min(self.get_elapsed_seconds() / self.get_defined_duration(), 1.0), 2) if self.get_defined_duration() else 0.0
        return max(tot_exec, tot_time)

    def get_executions_started(self) -> int:
        return self.run_control["global_executions"]

    def get_executions_completed(self) -> int:
        return self.get_ok() + self.get_ko()

    def get_ok(self) -> int:
        return self.run_control["global_ok"]

    def get_ko(self) -> int:
        return self.run_control["global_ko"]

    def get_executions_missing(self):
        return max(self.get_max_executions() - self.get_executions_completed(), 0)

    def get_success_ratio(self) -> float:
        if self.get_executions_completed():
            return self.get_ok() / self.get_executions_completed()
        return 1.0

    def get_success_ratio_overall(self) -> float:
        if self.get_max_executions():
            return self.get_ok() / self.get_max_executions()
        return 1.0

    def get_start_timestamp(self) -> float:
        return self.run_control["global_start_time"]

    def get_elapsed_seconds(self) -> float:
        if self.is_running():
            return time() - self.get_start_timestamp()
        return self.get_real_end_timestamp() - self.get_start_timestamp()

    def get_defined_end_timestamp(self) -> float:
        return self.run_control["global_end_time"]

    def get_real_end_timestamp(self) -> float:
        return self.run_control["global_real_end_time"]

    def get_last_run_timestamp(self) -> float:
        return self.run_control["global_last_run_timestamp"]

    def get_executions_call_period(self):
        return self.get_last_run_timestamp() - self.get_start_timestamp() + self.get_defined_burst_ts()

    def get_real_rps(self) -> float:
        ep = self.get_executions_call_period()
        es = self.get_executions_started()
        if ep and es > 0:
            return round(es / ep, 2)
        return 1.0

    def get_statistics(self) -> dict:
        return {"start_time": self.get_start_timestamp(),
                "end_time": self.get_real_end_timestamp(),
                "start": datetime.fromtimestamp(self.get_start_timestamp()).strftime("%Y-%m-%d %H:%M:%S.%f"),
                "end": datetime.fromtimestamp(self.get_real_end_timestamp()).strftime("%Y-%m-%d %H:%M:%S.%f"),
                "max_requests": self.get_max_executions(),
                "requests_started": self.get_executions_started(),
                "requests_completed": self.get_executions_completed(),
                "requests_missing": max(self.get_max_executions() - self.get_executions_completed(), 0),
                "execution_seconds": self.get_executions_call_period(),
                "elapsed_seconds": self.get_elapsed_seconds(),
                "rps": self.get_real_rps(),
                "percentage_complete": self.get_percentage_complete(),
                "success_ratio": self.get_success_ratio(),
                "overall_success_ratio": self.get_success_ratio_overall(),
                "ok": self.get_ok(),
                "ko": self.get_ko(),
                "block": self._get_block_id(),
                "ts": self.get_defined_burst_ts(),
                "safe_ts": self.get_user_threadsafe_period()}

    def _get_thread_method(self):
        return self.run_control["method"]

    def _get_thread_method_args(self):
        return self.run_control["args"]

    def _get_thread_method_kwargs(self):
        return self.run_control["kwargs"]

    def _get_workers(self) -> set:
        return self.run_control["thread_list"]

    def _add_worker(self, worker):
        self.run_control["thread_list"].append(worker)

    def _init_rc_global(self, run_method, run_args, run_kwargs):
        self.run_control["running"] = True
        self.run_control["method"] = run_method
        self.run_control["args"] = run_args
        self.run_control["kwargs"] = run_kwargs

        self._init_rc_block_first_time()

        now = time()
        self.run_control["global_executions"] = 0
        self.run_control["global_start_time"] = now
        self.run_control["global_end_time"] = now + self.get_defined_duration() if self.get_defined_duration() else None
        self.run_control["global_last_run_timestamp"] = now
        self.run_control["global_real_end_time"] = now
        self.run_control["ok"] = 0
        self.run_control["ko"] = 0

    def _inc_rc_executions(self, user: int):
        self.run_control["global_executions"] += 1
        self.run_control["global_last_run_timestamp"] = max(time(), self.run_control["global_last_run_timestamp"])
        self.run_control["block"]["requests_left"] -= 1
        self._add_worker_as_busy(user)

    def _get_rc_block_end_time(self) -> float:
        return self.run_control["block"]["ends_at"]

    def _get_rc_block_busy_end_time(self) -> float:
        return self.run_control["block"]["busy_until"]

    def _get_rc_block_next_run(self) -> float:
        return self.run_control["block"]["next_run"]

    def _set_rc_block_next_run(self, when):
        self.run_control["block"]["next_run"] = when + self.get_defined_burst_ts()

    def _get_rc_block_requests_left(self) -> int:
        return self.run_control["block"]["requests_left"]

    def _get_block_id(self) -> int:
        return self.run_control["block"]["id"]

    def _add_worker_as_busy(self, user):
        self.run_control["busy_workers"].add(user)

    def _remove_worker_as_busy(self, user):
        try:
            self.run_control["busy_workers"].remove(user)
        except Exception as e:
            pass

    def _get_busy_workers(self) -> set:
        return self.run_control["busy_workers"]

    def _has_reached_the_end(self) -> bool:
        if not self.is_running():
            return True
        if self.get_defined_executions() and self.get_executions_started() >= self.get_defined_executions():
            return True
        if self.get_defined_end_timestamp() and time() >= self.get_defined_end_timestamp():
            return True
        return False

    def _init_rc_block_first_time(self):
        self.run_control["block"] = dict()

        now = time()
        self.run_control["block"]["next_run"] = now
        self.run_control["block"]["ends_at"] = now
        self.run_control["block"]["busy_until"] = now
        self.run_control["block"]["requests_left"] = 0  # this is important
        self.run_control["block"]["id"] = 0

    def _init_next_rc_block(self):
        # if the block should end later than now (which its normal case, unless requests gets dragging)
        now = time()
        if self._get_rc_block_end_time() > now:
            now = self._get_rc_block_end_time()

        self.run_control["block"]["next_run"] = now + self.get_defined_burst_ts()
        self.run_control["block"]["ends_at"] = now + self.get_defined_burst_duration()
        self.run_control["block"]["busy_until"] = now + self.get_defined_burst_busy()
        self.run_control["block"]["requests_left"] = self.get_defined_burst_requests()
        self.run_control["block"]["id"] += 1

    def _sleep_until_end_of_block_and_init_new_one(self):
        # save for sleep later, after initialing a new block
        block_end_time = self._get_rc_block_end_time()    # could be min(.., self.get_rc_global_end_time()) if defined

        # if block ends after global_end_time definition, just end now
        if self.get_defined_end_timestamp() and block_end_time > self.get_defined_end_timestamp():
            self.stop(gracefully=True)
            raise TimeoutError("Must end now. block_end_time > global_end_time")

        # init new block before sleep, to be more accurate
        self._init_next_rc_block()

        # sleep until end of block
        safe_sleep(block_end_time - time())

    def _wait_for_next_task(self):
        next_run = self._get_rc_block_next_run()

        # if next_run is after global_end_time definition, just end now
        if self.get_defined_end_timestamp() and next_run > self.get_defined_end_timestamp():
            raise TimeoutError("Must end now. next_run > global_end_time")

        now = time()
        if next_run > now:
            # if need to wait for next task, go ahead and setup new block and then sleep
            self._set_rc_block_next_run(next_run)
            safe_sleep(next_run - time())
        else:
            # task already late so, setup new one after now
            self._set_rc_block_next_run(now)

    def _has_task(self, user: int, lock: Lock) -> int:
        lock.acquire()

        if self._has_reached_the_end():
            lock.release()
            return 0

        try:
            if self._get_rc_block_requests_left() == 0:
                self._sleep_until_end_of_block_and_init_new_one()
            else:
                self._wait_for_next_task()

            block_id = self._get_block_id()
            self._inc_rc_executions(user)
        except Exception:
            lock.release()
            return 0

        lock.release()
        return block_id

    def _inc_success_result(self, success: bool):
        if success:
            self.run_control["global_ok"] += 1
        else:
            self.run_control["global_ko"] += 1

    def _add_to_execution_log(self, start_time: float, end_time: float, success:bool, request_result: object, user: int, block_id: int, stat_lock: Lock):
        stat_lock.acquire()
        self._inc_success_result(success)
        self.execution_log.append((start_time, end_time, success, user, block_id, len(self._get_busy_workers()), request_result))
        self._remove_worker_as_busy(user)
        total_finished = self.get_executions_completed()
        stat_lock.release()

        # call notifier if total_finished reached the notification period
        self._notify_by_exec(total_finished)

    def _notify_by_exec(self, total_finished):
        if self.notifier["every_exec"] and self.notifier["method"]:
            if total_finished % self.notifier["every_exec"] == 0:
                # self._notify_progress(f"finished={total_finished}")
                Thread(target=self._notify_progress, args=(f"finished={total_finished}",)).start()

    def _notify_by_time(self):
        def run_in_thread(notify_interval):
            sleep_duration = notify_interval - 0.001
            while True:
                start_time = time()
                safe_sleep(sleep_duration)
                if self.is_running():
                    self._notify_progress(f"elapsed={self.get_elapsed_seconds():.3f}")
                    sleep_duration = 2*notify_interval - (time() - start_time) - 0.001
                else:
                    break

        if self.notifier["every_sec"]:
            Thread(target=run_in_thread, args=(self.notifier["every_sec"],)).start()

    def _notify_progress(self, cause: str):
        try:
            func = self.notifier["method"]
            args = self.notifier["args"]
            kwargs = self.notifier["kwargs"]
            stats = {"time": str(datetime.now()),
                     "users_busy": len(self._get_busy_workers()),
                     "cause": cause}
            stats.update(self.get_statistics())
            func(stats, *args, **kwargs)
        except Exception as e:
            pass

    # </editor-fold>

    # <editor-fold desc=" -= Thread methods =- ">

    def _worker_function(self, user: int, run_lock: Lock, stat_lock: Lock):
        while True:
            block_id = self._has_task(user, run_lock)
            if not block_id:
                break

            func = self._get_thread_method()
            args = self._get_thread_method_args()
            kwargs = self._get_thread_method_kwargs()
            start_time = time()

            try:
                request_result = func(user, *args, **kwargs)
                success = True if request_result else False
            except Exception as e:
                request_result = str(e)
                success = False

            self._add_to_execution_log(start_time, time(), success, request_result, user, block_id, stat_lock)

    def start(self, run_method, *run_args, **run_kwargs):
        if self.is_running():
            raise RuntimeError("Still running. Can't start new run before ending last one. Try to stop it first.")

        # lock for workers getting a new task (when the time to execute has come) and writing stats
        run_lock = Lock()
        stat_lock = Lock()

        # setup running global and block timers
        self._init_rc_global(run_method, run_args, run_kwargs)

        # start timed notify, if defined
        self._notify_by_time()

        # start threads
        for user in range(1, self.get_defined_users() + 1):
            worker = Thread(target=self._worker_function, args=(user, run_lock, stat_lock))
            worker.start()
            self._add_worker(worker)

        # wait for threads to finish
        for worker in self._get_workers():
            if worker.is_alive():
                try:
                    worker.join()
                except:
                    pass

        # record ending
        self.stop(gracefully=True)

        return self

    def stop(self, gracefully=True):
        self.run_control["global_real_end_time"] = time()
        self.run_control["running"] = False

        if not gracefully:
            for worker in self._get_workers():
                try:
                    worker.kill()
                except:
                    pass

        return self

    # </editor-fold>

    def __str__(self):
        return f"{__class__.__name__} {self.run_param}".replace("'", "\"")


def safe_sleep(sec: float):
    if sec > 0.0:
        sleep(sec)
