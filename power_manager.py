import ctypes
import sys

class PowerManager:
    """
    Manages Windows system execution state to ensure 24/7 background monitoring,
    allowing the display to turn off while keeping CPU and network interfaces active
    when the workstation is locked.
    """
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040

    _is_preventing_sleep = False

    @classmethod
    def set_prevent_sleep(cls, enable: bool):
        if sys.platform != "win32":
            return
        try:
            if enable:
                # Away mode keeps system running with active network/CPU while screen can turn off/lock
                res = ctypes.windll.kernel32.SetThreadExecutionState(
                    cls.ES_CONTINUOUS | cls.ES_SYSTEM_REQUIRED | cls.ES_AWAYMODE_REQUIRED
                )
                if res == 0:
                    # Fallback if AwayMode is not supported on this Windows edition
                    ctypes.windll.kernel32.SetThreadExecutionState(
                        cls.ES_CONTINUOUS | cls.ES_SYSTEM_REQUIRED
                    )
                cls._is_preventing_sleep = True
            else:
                # Restore default Windows sleep behavior
                ctypes.windll.kernel32.SetThreadExecutionState(cls.ES_CONTINUOUS)
                cls._is_preventing_sleep = False
        except Exception:
            pass

    @classmethod
    def allow_sleep(cls):
        cls.set_prevent_sleep(False)
