#!/usr/bin/env python3
"""
scale_test.py
~~~~~~~~~~~~~
Duration-based high-concurrency scale test for the Greeting service.

All threads run continuously for the full --duration (default 60 s).
System resources (CPU, memory, file descriptors, threads, I/O, network)
are sampled before, every second during, and after each target run.

Targets:
  1. Greeting.build()     — pure in-process greeting construction
  2. QuoteProvider.get()  — shuffle-deck quote selection under thread contention
  3. QuoteService TCP     — real socket connections to the RFC 865 server (opt-in)

Usage::

    python3 tests/scale_test.py                              # 60 s, 20 threads
    python3 tests/scale_test.py -d 60 -c 50
    python3 tests/scale_test.py --tcp --tcp-port 19865
    python3 tests/scale_test.py --no-greeting --no-quote --tcp
    python3 tests/scale_test.py --help
"""

import argparse
import os
import socket
import statistics
import sys
import threading
import time

import psutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from greeting import Greeting
from quote_provider import QuoteProvider
from quote_service import QuoteService

# ── ANSI ─────────────────────────────────────────────────────────────────────
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_SEP    = "─" * 62
_SEP2   = "·" * 62


def _fmt_ns(ns) -> str:
    ns = float(ns)
    if ns >= 1_000_000_000:
        return f"{ns / 1_000_000_000:.3f} s"
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.3f} ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.3f} µs"
    return f"{ns:.0f} ns"


def _fmt_bytes(b) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _percentile(sorted_data: list, pct: int):
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    idx = max(0, int((pct / 100.0) * n) - 1)
    return sorted_data[min(idx, n - 1)]


# ── Resource snapshot ─────────────────────────────────────────────────────────

def _resource_snapshot(proc: psutil.Process) -> dict:
    """Capture a point-in-time resource snapshot for this process + system."""
    # Prime CPU measurement (first call returns 0.0)
    proc.cpu_percent()
    time.sleep(0.1)
    cpu_proc = proc.cpu_percent()

    mem   = proc.memory_info()
    try:
        fds   = proc.num_fds()
    except AttributeError:
        fds   = -1   # Windows
    try:
        conns = len(proc.net_connections())
    except (psutil.AccessDenied, AttributeError):
        conns = -1

    thr   = proc.num_threads()
    vmem  = psutil.virtual_memory()
    swap  = psutil.swap_memory()
    cpu_sys = psutil.cpu_percent(interval=None)

    try:
        io = proc.io_counters()
        io_read  = io.read_bytes
        io_write = io.write_bytes
    except (psutil.AccessDenied, AttributeError):
        io_read = io_write = -1

    return {
        "ts":          time.time(),
        "cpu_proc":    cpu_proc,       # % this process
        "cpu_sys":     cpu_sys,        # % all CPUs (system-wide)
        "rss":         mem.rss,        # resident set size bytes
        "vms":         mem.vms,        # virtual memory bytes
        "mem_pct":     vmem.percent,   # system RAM used %
        "swap_pct":    swap.percent,   # swap used %
        "fds":         fds,            # open file descriptors
        "threads":     thr,            # OS threads in this process
        "connections": conns,          # open TCP/UDP connections
        "io_read":     io_read,        # cumulative bytes read
        "io_write":    io_write,       # cumulative bytes written
    }


def _print_resource_report(label: str,
                            before: dict,
                            after: dict,
                            samples: list) -> None:
    """Print before/peak/after resource table."""
    print(f"\n  {_DIM}System Resources — {label}{_RESET}")
    print(f"  {_DIM}{_SEP2}{_RESET}")

    # CPU
    cpu_samples = [s["cpu_proc"] for s in samples] or [0]
    print(f"  {'CPU (process)':20s}  "
          f"before={before['cpu_proc']:5.1f}%  "
          f"peak={max(cpu_samples):5.1f}%  "
          f"avg={statistics.mean(cpu_samples):5.1f}%  "
          f"after={after['cpu_proc']:5.1f}%")

    cpu_sys_samples = [s["cpu_sys"] for s in samples] or [0]
    print(f"  {'CPU (system)':20s}  "
          f"before={before['cpu_sys']:5.1f}%  "
          f"peak={max(cpu_sys_samples):5.1f}%  "
          f"avg={statistics.mean(cpu_sys_samples):5.1f}%  "
          f"after={after['cpu_sys']:5.1f}%")

    # Memory
    rss_samples = [s["rss"] for s in samples] or [before["rss"]]
    print(f"  {'RSS memory':20s}  "
          f"before={_fmt_bytes(before['rss']):>10s}  "
          f"peak={_fmt_bytes(max(rss_samples)):>10s}  "
          f"after={_fmt_bytes(after['rss']):>10s}  "
          f"delta={_fmt_bytes(after['rss'] - before['rss']):>10s}")

    mem_samples = [s["mem_pct"] for s in samples] or [0]
    print(f"  {'System RAM':20s}  "
          f"before={before['mem_pct']:5.1f}%  "
          f"peak={max(mem_samples):5.1f}%  "
          f"after={after['mem_pct']:5.1f}%")

    # Threads & FDs
    thr_samples = [s["threads"] for s in samples] or [before["threads"]]
    print(f"  {'OS threads':20s}  "
          f"before={before['threads']:>5d}  "
          f"peak={max(thr_samples):>5d}  "
          f"after={after['threads']:>5d}")

    if before["fds"] >= 0:
        fd_samples = [s["fds"] for s in samples] or [before["fds"]]
        print(f"  {'File descriptors':20s}  "
              f"before={before['fds']:>5d}  "
              f"peak={max(fd_samples):>5d}  "
              f"after={after['fds']:>5d}")

    if before["connections"] >= 0:
        conn_samples = [s["connections"] for s in samples] or [0]
        print(f"  {'TCP connections':20s}  "
              f"before={before['connections']:>5d}  "
              f"peak={max(conn_samples):>5d}  "
              f"after={after['connections']:>5d}")

    # I/O delta
    if before["io_read"] >= 0:
        read_delta  = after["io_read"]  - before["io_read"]
        write_delta = after["io_write"] - before["io_write"]
        print(f"  {'Disk I/O (delta)':20s}  "
              f"read={_fmt_bytes(read_delta):>10s}  "
              f"write={_fmt_bytes(write_delta):>10s}")

    # Swap
    if before["swap_pct"] > 0 or after["swap_pct"] > 0:
        swap_samples = [s["swap_pct"] for s in samples] or [0]
        print(f"  {'Swap':20s}  "
              f"before={before['swap_pct']:5.1f}%  "
              f"peak={max(swap_samples):5.1f}%  "
              f"after={after['swap_pct']:5.1f}%")


# ── Resource sampler (background thread) ─────────────────────────────────────

class _ResourceSampler:
    """Samples process + system resources every `interval` seconds."""

    def __init__(self, proc: psutil.Process, interval: float = 1.0):
        self._proc     = proc
        self._interval = interval
        self._samples: list = []
        self._stop     = threading.Event()
        self._thread   = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> list:
        self._stop.set()
        self._thread.join(timeout=5)
        return self._samples

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                snap = _resource_snapshot(self._proc)
                self._samples.append(snap)
            except Exception:
                pass
            self._stop.wait(self._interval)


# ── Progress ticker ───────────────────────────────────────────────────────────

class _ProgressTicker:
    """Prints a live one-line progress update every second."""

    def __init__(self, duration_s: int, counter: list):
        self._duration   = duration_s
        self._counter    = counter
        self._stop       = threading.Event()
        self._thread     = threading.Thread(target=self._loop, daemon=True)
        self._snapshots: list = []
        self._prev_count = 0
        self._start_time = 0.0

    def start(self, start_time: float) -> None:
        self._start_time = start_time
        self._thread.start()

    def stop(self) -> list:
        self._stop.set()
        self._thread.join(timeout=3)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return self._snapshots

    def _loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(1.0)
            elapsed = time.perf_counter() - self._start_time
            current = self._counter[0]
            rps     = current - self._prev_count
            self._prev_count = current
            self._snapshots.append((int(elapsed), rps))
            pct = min(100, int(elapsed / self._duration * 100))
            bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
            sys.stdout.write(
                f"\r  {_CYAN}{bar}{_RESET}  {pct:3d}%  "
                f"{elapsed:5.1f}s/{self._duration}s  "
                f"{_BOLD}{rps:,} req/s{_RESET}  total={current:,}   "
            )
            sys.stdout.flush()


# ── Results printer ───────────────────────────────────────────────────────────

def _print_results(label: str, durations_ns: list, errors: int,
                   elapsed_s: float, snapshots: list,
                   res_before: dict, res_after: dict,
                   res_samples: list) -> None:
    total = len(durations_ns) + errors
    s = sorted(durations_ns)
    ok = len(s)
    error_rate = 100.0 * errors / total if total else 0.0
    throughput = ok / elapsed_s if elapsed_s > 0 else 0.0
    er_col = _GREEN if error_rate == 0 else (_YELLOW if error_rate < 5 else _RED)

    print(f"\n{_CYAN}{_SEP}{_RESET}")
    print(f"  {_BOLD}{label}{_RESET}")
    print(f"{_CYAN}{_SEP}{_RESET}")
    print(f"  duration   : {elapsed_s:.1f} s")
    print(f"  requests   : {total:,}  (ok={ok:,}, errors={errors:,})")
    print(f"  error rate : {er_col}{error_rate:.2f}%{_RESET}")
    print(f"  throughput : {_BOLD}{throughput:,.1f} req/s{_RESET}  (overall)")

    if snapshots:
        # Drop the last tick — it covers the wind-down period after stop_event
        # is set, so its rps is artificially low and skews the min.
        tputs = [r for _, r in snapshots[:-1] if r > 0]
        if tputs:
            print(f"  tput  min  : {min(tputs):,.1f} req/s")
            print(f"  tput  max  : {max(tputs):,.1f} req/s")
            print(f"  tput  avg  : {statistics.mean(tputs):,.1f} req/s")

    if s:
        print(f"  {_DIM}{'─'*42}{_RESET}")
        print(f"  latency min: {_fmt_ns(s[0])}")
        print(f"  latency avg: {_fmt_ns(statistics.mean(s))}")
        print(f"  latency p50: {_fmt_ns(statistics.median(s))}")
        print(f"  latency p95: {_fmt_ns(_percentile(s, 95))}")
        print(f"  latency p99: {_fmt_ns(_percentile(s, 99))}")
        print(f"  latency max: {_fmt_ns(s[-1])}")

    # ── Resource report ───────────────────────────────────────────────────
    _print_resource_report(label, res_before, res_after, res_samples)

    print(f"{_CYAN}{_SEP}{_RESET}")

    # Per-second throughput sparkline (drop wind-down tick)
    if snapshots:
        valid = [(sec, rps) for sec, rps in snapshots[:-1] if rps > 0]
        if valid:
            max_rps = max(r for _, r in valid)
            print(f"  {_DIM}Throughput over time:{_RESET}")
            for sec, rps in valid:
                bar_len = min(38, int(rps / max_rps * 38))
                bar = "█" * bar_len
                print(f"    {sec:>4}s  {bar:<38}  {rps:,.0f} req/s")


# ── Duration-based worker harness ─────────────────────────────────────────────

def _run_duration(label: str, duration_s: int, concurrency: int,
                  make_worker_fn) -> None:
    proc       = psutil.Process()
    stop_event = threading.Event()
    durations: list = []
    error_count = [0]
    ok_count    = [0]
    lock        = threading.Lock()
    batch_size  = 50   # flush local buffer to shared list every N ops

    def thread_body(work_fn):
        local_d = []
        local_e = 0
        flush_at = batch_size
        while not stop_event.is_set():
            try:
                ns = work_fn()
                local_d.append(ns)
            except Exception:
                local_e += 1
            if len(local_d) >= flush_at:
                with lock:
                    # Cap total stored samples to 500k to bound memory usage.
                    # Beyond that we still count ops but discard the raw ns value.
                    space = max(0, 500_000 - len(durations))
                    if space > 0:
                        durations.extend(local_d[:space])
                    ok_count[0] += len(local_d)
                local_d = []
                flush_at = batch_size
        # flush remainder
        with lock:
            space = max(0, 500_000 - len(durations))
            if space > 0:
                durations.extend(local_d[:space])
            error_count[0] += local_e
            ok_count[0] += len(local_d)

    work_fns = [make_worker_fn() for _ in range(concurrency)]

    print(f"\n{_CYAN}{_SEP}{_RESET}")
    print(f"  {_BOLD}{label}{_RESET}")
    print(f"  {_DIM}Threads: {concurrency}   Duration: {duration_s}s{_RESET}")

    # ── Before snapshot ───────────────────────────────────────────────────
    print(f"  {_DIM}Capturing baseline resource snapshot...{_RESET}")
    res_before = _resource_snapshot(proc)

    sampler = _ResourceSampler(proc, interval=1.0)
    ticker  = _ProgressTicker(duration_s, ok_count)

    t_start = time.perf_counter()
    sampler.start()
    ticker.start(t_start)

    threads = [threading.Thread(target=thread_body, args=(fn,), daemon=True)
               for fn in work_fns]
    for t in threads:
        t.start()

    time.sleep(duration_s)
    stop_event.set()

    for t in threads:
        t.join(timeout=10)

    elapsed     = time.perf_counter() - t_start
    snapshots   = ticker.stop()
    res_samples = sampler.stop()

    # ── After snapshot ────────────────────────────────────────────────────
    res_after = _resource_snapshot(proc)

    _print_results(
        label, durations, error_count[0], elapsed,
        snapshots, res_before, res_after, res_samples,
    )


# ── Target factories ──────────────────────────────────────────────────────────

def _greeting_worker_factory():
    g   = Greeting("ScaleTest")
    now = datetime(2026, 3, 22, 9, 0)
    def work():
        t0 = time.perf_counter_ns()
        g.build(now)
        return time.perf_counter_ns() - t0
    return work


def _quote_worker_factory(provider, lock):
    def work():
        t0 = time.perf_counter_ns()
        with lock:
            provider.get()
        return time.perf_counter_ns() - t0
    return work


def _tcp_worker_factory(port):
    def work():
        t0 = time.perf_counter_ns()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            s.recv(1024)
        return time.perf_counter_ns() - t0
    return work


# ── Target runners ────────────────────────────────────────────────────────────

def run_greeting(duration_s: int, concurrency: int) -> None:
    _run_duration(
        label          = f"Greeting.build()  [{concurrency} threads, {duration_s}s]",
        duration_s     = duration_s,
        concurrency    = concurrency,
        make_worker_fn = _greeting_worker_factory,
    )


def run_quote_provider(duration_s: int, concurrency: int) -> None:
    provider = QuoteProvider()
    lock_p   = threading.Lock()
    _run_duration(
        label          = f"QuoteProvider.get()  [{concurrency} threads, {duration_s}s]",
        duration_s     = duration_s,
        concurrency    = concurrency,
        make_worker_fn = lambda: _quote_worker_factory(provider, lock_p),
    )


def run_tcp(duration_s: int, concurrency: int, port: int) -> None:
    provider   = QuoteProvider()
    service    = QuoteService(provider=provider, port=port)
    srv_thread = threading.Thread(target=service.start_tcp, daemon=True)
    srv_thread.start()
    time.sleep(0.2)

    _run_duration(
        label          = f"QuoteService TCP  [{concurrency} threads, {duration_s}s, :{port}]",
        duration_s     = duration_s,
        concurrency    = concurrency,
        make_worker_fn = lambda: _tcp_worker_factory(port),
    )

    service.stop()
    srv_thread.join(timeout=3)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Duration-based high-concurrency scale test with resource monitoring.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-d", "--duration", type=int, default=60,
        help="Seconds to run each target (default: 60)")
    parser.add_argument("-c", "--concurrency", type=int, default=20,
        help="Concurrent threads per target (default: 20)")
    parser.add_argument("--tcp", action="store_true",
        help="Also run the TCP QuoteService target")
    parser.add_argument("--tcp-port", type=int, default=19865,
        help="Port for TCP target (default: 19865)")
    parser.add_argument("--no-greeting", action="store_true",
        help="Skip Greeting.build() target")
    parser.add_argument("--no-quote", action="store_true",
        help="Skip QuoteProvider.get() target")
    args = parser.parse_args()

    n_targets = (0 if args.no_greeting else 1) + \
                (0 if args.no_quote    else 1) + \
                (1 if args.tcp         else 0)

    print(f"\n{_BOLD}Scale Test{_RESET}  "
          f"duration={args.duration}s  concurrency={args.concurrency}  "
          f"targets={n_targets}  "
          f"~{n_targets * args.duration}s total")
    print(f"  {_DIM}psutil {psutil.__version__} — "
          f"CPUs={psutil.cpu_count()}  "
          f"RAM={_fmt_bytes(psutil.virtual_memory().total)}{_RESET}")

    if not args.no_greeting:
        run_greeting(args.duration, args.concurrency)

    if not args.no_quote:
        run_quote_provider(args.duration, args.concurrency)

    if args.tcp:
        run_tcp(args.duration, args.concurrency, args.tcp_port)

    print()


if __name__ == "__main__":
    main()
