"""Threshold logic: each threshold fires only once per discharge."""
WARNING = "warning"
CRITICAL = "critical"


class LowBatteryAlerts:
    def __init__(self, warn, critical):
        self.warn = warn
        self.critical = critical
        self._armed = {WARNING: True, CRITICAL: True}

    def update(self, level, charging):
        """Returns WARNING, CRITICAL or None (None = no notification needed)."""
        if level is None:
            return None
        if charging:
            self._armed = {WARNING: True, CRITICAL: True}
            return None
        if level > self.warn:
            self._armed[WARNING] = True
        if level > self.critical:
            self._armed[CRITICAL] = True

        if level <= self.critical and self._armed[CRITICAL]:
            # The critical notification replaces the warning if both are due at the same time.
            self._armed = {WARNING: False, CRITICAL: False}
            return CRITICAL
        if level <= self.warn and level > self.critical and self._armed[WARNING]:
            self._armed[WARNING] = False
            return WARNING
        return None


class FullChargeDetector:
    """Detects "fully charged" from the voltage (the percentage is useless while charging).

    Heuristic: at the end of a charge the voltage hardly rises any more. If it rises by at most
    `max_rise_mv` over `window_s` seconds and is above `min_mv`, the battery counts as full.
    Reports once per charge.
    """

    def __init__(self, window_s=600, max_rise_mv=5, min_mv=4100):
        self.window_s = window_s
        self.max_rise_mv = max_rise_mv
        self.min_mv = min_mv
        self._samples = []  # (time, mV) since the start of the charge
        self._reported = False

    def update(self, now, voltage_mv, charging):
        """True exactly once, when the battery counts as full."""
        if not charging or voltage_mv is None:
            self._samples, self._reported = [], False
            return False
        self._samples.append((now, voltage_mv))
        self._samples = [s for s in self._samples if now - s[0] <= self.window_s]
        if self._reported or now - self._samples[0][0] < self.window_s * 0.9:
            return False  # window not nearly full yet
        volts = [v for _, v in self._samples]
        if min(volts) >= self.min_mv and max(volts) - min(volts) <= self.max_rise_mv:
            self._reported = True
            return True
        return False
