"""Cumulative OS counters for one supervised child process.

Only aggregate counters are read: transferred byte totals and CPU time. No
payload, command line, environment or memory content is inspected. Sampling is
best effort: an unavailable counter is reported as absent, never fabricated.
"""
import ctypes
import os
import threading
import time

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ACCESS = PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION


class _IoCounters(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]

    def seconds(self):
        return ((self.dwHighDateTime << 32) | self.dwLowDateTime) / 10_000_000


def supported():
    return os.name == 'nt'


def sample(pid):
    """Return cumulative counters for pid, or {} when the OS cannot report them."""
    if not supported() or not pid:
        return {}
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        handle = kernel32.OpenProcess(_ACCESS, False, int(pid))
        if not handle:
            # Limited rights can still expose CPU time but not I/O totals.
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return {}
        try:
            counters = {}
            io = _IoCounters()
            kernel32.GetProcessIoCounters.argtypes = (ctypes.c_void_p, ctypes.POINTER(_IoCounters))
            if kernel32.GetProcessIoCounters(handle, ctypes.byref(io)):
                counters.update(read_bytes=int(io.ReadTransferCount), write_bytes=int(io.WriteTransferCount),
                                other_bytes=int(io.OtherTransferCount), read_ops=int(io.ReadOperationCount),
                                write_ops=int(io.WriteOperationCount))
            created, exited, kernel, user = _FileTime(), _FileTime(), _FileTime(), _FileTime()
            kernel32.GetProcessTimes.argtypes = (ctypes.c_void_p, ctypes.POINTER(_FileTime), ctypes.POINTER(_FileTime),
                                                 ctypes.POINTER(_FileTime), ctypes.POINTER(_FileTime))
            if kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                       ctypes.byref(kernel), ctypes.byref(user)):
                counters['cpu_seconds'] = round(kernel.seconds() + user.seconds(), 3)
            return counters
        finally:
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle(handle)
    except (OSError, AttributeError, ValueError):
        return {}


def activity_total(pid):
    """Cumulative fingerprint used only to detect that work is still happening.

    Byte totals and CPU time are compared for inequality, never interpreted as
    progress of the answer itself.
    """
    values = sample(pid)
    if not values:
        return None
    return (values.get('read_bytes', 0), values.get('write_bytes', 0),
            values.get('other_bytes', 0), values.get('cpu_seconds', 0.0))


class Sampler:
    """Periodic counter samples for one pid; never raises into the caller.

    The counters separate "socket is delivering data" from "supervisor sees no
    progress": a stalled child whose read totals keep growing is still receiving
    bytes, which is a different fault than a silent peer.
    """

    def __init__(self, pid, interval=2.0):
        self.pid = pid
        self.interval = interval
        self.started = time.monotonic()
        self.samples = []
        self._done = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if not supported() or not self.pid:
            return self
        self.samples.append(dict(self._read(), elapsed_seconds=0.0))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _read(self):
        counters = sample(self.pid)
        return counters

    def _loop(self):
        while not self._done.wait(self.interval):
            values = self._read()
            if not values:
                continue
            with self._lock:
                self.samples.append(dict(values, elapsed_seconds=round(time.monotonic() - self.started, 3)))

    def latest(self):
        """Most recent sample, or {} when counters are unavailable."""
        with self._lock:
            return self.samples[-1] if self.samples else {}

    def mark(self, name):
        values = self._read()
        if values:
            with self._lock:
                self.samples.append(dict(values, elapsed_seconds=round(time.monotonic() - self.started, 3),
                                         mark=name))

    def stop(self):
        self._done.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        final = self._read()
        if final:
            with self._lock:
                self.samples.append(dict(final, elapsed_seconds=round(time.monotonic() - self.started, 3),
                                         mark='stop'))
        return self.summary()

    def summary(self):
        with self._lock:
            samples = list(self.samples)
        if not samples:
            return {'available': False}
        reads = [s['read_bytes'] for s in samples if 'read_bytes' in s]
        writes = [s['write_bytes'] for s in samples if 'write_bytes' in s]
        cpu = [s['cpu_seconds'] for s in samples if 'cpu_seconds' in s]
        summary = {'available': bool(reads or cpu), 'samples': len(samples), 'interval_seconds': self.interval,
                   'read_bytes_growth': (reads[-1] - reads[0]) if reads else None,
                   'write_bytes_growth': (writes[-1] - writes[0]) if writes else None,
                   'cpu_seconds_growth': round(cpu[-1] - cpu[0], 3) if cpu else None,
                   'last_elapsed_seconds': samples[-1].get('elapsed_seconds')}
        # Growth between the last two samples shows whether data was still
        # arriving when supervision ended.
        if len(reads) >= 2:
            summary['read_bytes_last_interval'] = reads[-1] - reads[-2]
        return summary

    def timeline(self, limit=120):
        with self._lock:
            samples = list(self.samples)
        if len(samples) <= limit:
            return samples
        step = len(samples) / float(limit)
        return [samples[min(len(samples) - 1, int(i * step))] for i in range(limit)]
