"""Schwellenlogik: jede Schwelle meldet sich pro Entladevorgang nur einmal."""
WARNING = "warning"
CRITICAL = "critical"


class LowBatteryAlerts:
    def __init__(self, warn, critical):
        self.warn = warn
        self.critical = critical
        self._armed = {WARNING: True, CRITICAL: True}

    def update(self, level, charging):
        """Gibt WARNING, CRITICAL oder None zurück (None = keine Meldung nötig)."""
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
            # Die kritische Meldung ersetzt die Warnung, wenn beide gleichzeitig fällig sind.
            self._armed = {WARNING: False, CRITICAL: False}
            return CRITICAL
        if level <= self.warn and level > self.critical and self._armed[WARNING]:
            self._armed[WARNING] = False
            return WARNING
        return None


class FullChargeDetector:
    """Erkennt "voll geladen" über die Spannung (der Prozentwert ist beim Laden unbrauchbar).

    Heuristik: Die Ladespannung steigt am Ende nur noch kaum. Steigt sie über `window_s`
    Sekunden um höchstens `max_rise_mv` und liegt sie über `min_mv`, gilt der Akku als voll.
    Meldet sich pro Ladevorgang einmal.
    """

    def __init__(self, window_s=600, max_rise_mv=5, min_mv=4100):
        self.window_s = window_s
        self.max_rise_mv = max_rise_mv
        self.min_mv = min_mv
        self._samples = []  # (Zeit, mV) seit Beginn des Ladevorgangs
        self._reported = False

    def update(self, now, voltage_mv, charging):
        """True genau einmal, wenn der Akku als voll gilt."""
        if not charging or voltage_mv is None:
            self._samples, self._reported = [], False
            return False
        self._samples.append((now, voltage_mv))
        self._samples = [s for s in self._samples if now - s[0] <= self.window_s]
        if self._reported or now - self._samples[0][0] < self.window_s * 0.9:
            return False  # Fenster noch nicht annähernd gefüllt
        volts = [v for _, v in self._samples]
        if min(volts) >= self.min_mv and max(volts) - min(volts) <= self.max_rise_mv:
            self._reported = True
            return True
        return False
