from dataclasses import dataclass, field
from typing import Callable, NamedTuple, Any


class ExecutionLog(NamedTuple):
    start_ts: float
    end_ts: float
    success: bool
    user: int
    block: int
    users_busy: int
    request_result: Any


@dataclass(init=True, repr=True, frozen=False)
class _WorkerBlock:
    id: int = 0
    requests_left: int = 0
    next_run: float = 0.0
    ends_at: float = 0.0
    busy_until: float = 0.0


@dataclass(init=True, repr=True, frozen=False)
class _RunControl:
    method: Callable = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    running: bool = False
    workers_thread_list: list = field(default_factory=list)
    workers_busy: set = field(default_factory=set)
    global_executions: int = 0
    global_start_time: float = 0.0
    global_end_time: float = 0.0
    global_last_run_timestamp: float = 0.0
    global_real_end_time: float = 0.0
    global_ok: int = 0
    global_ko: int = 0
    block: _WorkerBlock = field(default_factory=_WorkerBlock)


@dataclass(init=True, repr=True, frozen=False)
class _Notifier:
    method: Callable = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    every_exec: int = 0
    every_sec: int = 0


@dataclass(init=True, repr=True, frozen=True)
class _BurstBlock:
    req: int
    busy: float
    rps: float
    ts: float
    duration: float
    idle: float


@dataclass(init=True, repr=True, frozen=False)
class _RunParameters:
    users: int
    rps: float
    req: int
    dt_sec: float
    duration_sec: float
    executions: int
    block: _BurstBlock
    mode: str
    user_threadsafe_ts: float = 0.0
    max_executions: int = 0


@dataclass(init=True, repr=True, frozen=False)
class ThreadRegulatorStatistics:
    start_time: float = 0.0
    end_time: float = 0.0
    start: str = ""
    end: str = ""
    max_requests: int = 0
    requests_started: int = 0
    requests_completed: int = 0
    requests_missing: int = 0
    execution_seconds: int = 0
    elapsed_seconds: int = 0
    rps: float = 0.0
    percentage_complete: float = 0.0
    success_ratio: float = 0.0
    overall_success_ratio: float = 0.0
    ok: int = 0
    ko: int = 0
    block: int = 0
    ts: float = 0.0
    safe_ts: float = 0.0
