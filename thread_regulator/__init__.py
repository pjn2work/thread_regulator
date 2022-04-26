from thread_regulator.thread_mode import ThreadRegulator


__version__ = "1.0.0"


def create_regular(users: int, rps: float, duration_sec: float, executions: int) -> ThreadRegulator:
    return ThreadRegulator(users, rps, None, None, duration_sec, executions)


def create_burst(users: int, rps: float, req: int, dt_sec: float, duration_sec: float, executions: int) -> ThreadRegulator:
    return ThreadRegulator(users, rps, req, dt_sec, duration_sec, executions)
