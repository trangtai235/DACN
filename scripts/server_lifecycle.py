"""Tie the web server process tree to its Windows launcher lifetime."""
import ctypes
from ctypes import wintypes
import os


# Keep this non-inheritable handle alive until the launcher exits. Windows then
# closes it even if the terminal is closed or the launcher is forcibly stopped.
_job = None


def bind_server_lifetime():
    global _job
    if os.name != 'nt' or _job is not None:
        return

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
            ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
            ('max_working_set', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
            ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
            ('scheduling', wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
            ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
            ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    _job = job
