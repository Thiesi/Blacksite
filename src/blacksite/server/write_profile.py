"""Opt-in I/O-layer write probes used by S11/S40 acceptance.

Nothing is installed during normal service operation. Probes delegate the
same calls synchronously and restore instance attributes on exit. Counter
collection is bracketed: a slow clock/counter read is visible separately
from the operation, and wall minus CPU is not labelled as an I/O cause.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
import threading
import time
import sys
from typing import Any

try:
    import resource
except ImportError:  # Windows has clocks, but not Unix thread rusage.
    resource = None


COUNTERS = ("voluntary_switches", "involuntary_switches", "minor_faults",
            "major_faults", "input_blocks", "output_blocks")


@dataclass(frozen=True)
class Sample:
    began_ns: int
    ended_ns: int
    thread_ns: int
    process_ns: int
    counters: tuple[int, ...] | None


def sample() -> Sample:
    began = time.perf_counter_ns()
    thread, process = time.thread_time_ns(), time.process_time_ns()
    counters = None
    if resource is not None and hasattr(resource, "RUSAGE_THREAD"):
        usage = resource.getrusage(resource.RUSAGE_THREAD)
        counters = (usage.ru_nvcsw, usage.ru_nivcsw, usage.ru_minflt,
                    usage.ru_majflt, usage.ru_inblock, usage.ru_oublock)
    return Sample(began, time.perf_counter_ns(), thread, process, counters)


def difference(start: Sample, end: Sample) -> dict[str, Any]:
    return {
        "start_ns": start.ended_ns,
        "end_ns": end.began_ns,
        "wall_ms": (end.began_ns - start.ended_ns) / 1_000_000,
        "thread_cpu_ms": (end.thread_ns - start.thread_ns) / 1_000_000,
        "process_cpu_ms": (end.process_ns - start.process_ns) / 1_000_000,
        "sampling_wall_ms": ((start.ended_ns - start.began_ns)
                             + (end.ended_ns - end.began_ns)) / 1_000_000,
        "thread_counters": (dict(zip(COUNTERS, (b - a for a, b in
                            zip(start.counters, end.counters))))
                            if start.counters is not None and end.counters is not None else None),
    }


class ConnectionProbe:
    """Delegate to the storage-owned connection; record no SQL or values."""

    def __init__(self, connection: Any, probe: "WriteProfile") -> None:
        self.connection, self.probe = connection, probe

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)

    def __enter__(self) -> Any:
        return self.connection.__enter__()

    def __exit__(self, *args: Any) -> Any:
        label = "sqlite.rollback" if args[0] is not None else "sqlite.commit"
        return self.probe.measure(label, self.connection.__exit__, *args)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self.probe.measure("sqlite.execute", self.connection.execute, *args, **kwargs)

    def executemany(self, *args: Any, **kwargs: Any) -> Any:
        return self.probe.measure("sqlite.executemany", self.connection.executemany, *args, **kwargs)


class WriteProfile:
    """Measure only calls inside character writes; snapshot the actual gate.

    A status token identifies the immutable sample vector captured in that
    synchronous status call. Later ticks and status requests cannot change
    which samples the S11 assertion used. The normal status API is untouched
    outside this acceptance-only context.
    """

    def __init__(self, server: Any, *, reader: Callable[[], Sample] = sample) -> None:
        self.server, self.reader = server, reader
        self.loop = server.core.loop
        self.calls: deque[dict[str, Any]] = deque(maxlen=self.loop.timings.maxlen)
        self.gates: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.stack: list[int] = []
        self.restores: list[Callable[[], None]] = []

    def replace(self, target: Any, name: str, value: Any) -> None:
        existed = name in vars(target)
        previous = vars(target).get(name)
        setattr(target, name, value)
        def restore() -> None:
            if existed:
                setattr(target, name, previous)
            else:
                delattr(target, name)
        self.restores.append(restore)

    def wrap(self, target: Any, name: str, label: str | Callable[..., str]) -> None:
        if target is None or not hasattr(target, name):
            return
        original = getattr(target, name)
        @wraps(original)
        def measured(*args: Any, **kwargs: Any) -> Any:
            operation = label(*args, **kwargs) if callable(label) else label
            return self.measure(operation, original, *args, **kwargs)
        self.replace(target, name, measured)

    def measure(self, operation: str, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.current is None:
            return function(*args, **kwargs)
        entries = self.current["operations"]
        entry: dict[str, Any] = {"operation": operation,
                                 "parent": self.stack[-1] if self.stack else None}
        index = len(entries)
        entries.append(entry)
        self.stack.append(index)
        start = self.reader()
        try:
            return function(*args, **kwargs)
        finally:
            end = self.reader()
            self.stack.pop()
            entry.update(difference(start, end))

    def __enter__(self) -> "WriteProfile":
        original_writes, original_status = self.server._character_writes, self.server.status

        def writes() -> None:
            row: dict[str, Any] = {"tick": self.loop.last_tick,
                                   "thread": threading.get_ident(), "operations": []}
            self.current = row
            try:
                self.measure("character_writes", original_writes)
            finally:
                self.current = None
                self.calls.append(row)

        def status() -> dict[str, Any]:
            result = original_status()
            # No await occurs in status, and only the event-loop owner
            # records timings. This is the same vector timing() just used.
            values = list(self.loop.timings)
            token = len(self.gates)
            self.gates.append({"id": token, "samples_ms": values, "count": len(values),
                               "reported": dict(result["tick"])})
            return {**result, "_write_profile_gate": token}

        def dirty_label(kind: str, record_id: str, *args: Any, **kwargs: Any) -> str:
            # Meta keys name authored subsystems; never log player/item IDs
            # or any snapshot contents in an operation label.
            return "storage.mark_dirty:" + kind + (":" + record_id if kind == "meta" else "")

        try:
            self.replace(self.server, "_character_writes", writes)
            self.replace(self.server, "status", status)
            storage, core = self.server.storage, self.server.core
            # Server.start binds this callback before the probe is installed.
            self.replace(core, "status_provider", status)
            self.wrap(storage, "mark_dirty", dirty_label)
            for name in ("_json", "_flush", "character_write", "commerce_write", "report", "meta"):
                self.wrap(storage, name, "storage." + name)
            self.replace(storage, "db", ConnectionProbe(storage.db, self))
            self.wrap(getattr(core, "contracts", None), "record", "contracts.record")
            self.wrap(getattr(core, "characters", None), "committed", "characters.committed")
            for name in ("can_commit", "prepare", "committed"):
                self.wrap(getattr(core, "commerce", None), name, "commerce." + name)
            self.wrap(getattr(core, "lattice", None) and core.lattice.sources, "record", "lattice.record")
            self.wrap(getattr(core, "npcs", None) and core.npcs.spawners, "record", "npcs.record")
            for name in ("event", "audit"):
                self.wrap(getattr(self.server, "logs", None), name, "logs." + name)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args: Any) -> None:
        for restore in reversed(self.restores):
            restore()
        self.restores.clear()

    def gate(self, status: dict[str, Any]) -> dict[str, Any]:
        gate = self.gates[status["_write_profile_gate"]]
        return {**gate, "samples_ms": list(gate["samples_ms"]), "reported": dict(gate["reported"])}

    def metadata(self) -> dict[str, Any]:
        return {"clock_counters": "wall brackets, thread/process CPU; optional RUSAGE_THREAD deltas",
                "counter_order": list(COUNTERS), "gil_switch_interval_s": sys.getswitchinterval(),
                "threads": [{"name": thread.name, "ident": thread.ident} for thread in threading.enumerate()],
                "interpretation": "Wall minus CPU is not a cause. Inspect operation nesting, counter deltas and sampling brackets; null counters mean unsupported."}
