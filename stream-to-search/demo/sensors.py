"""Shared fleet simulator for the demo.

We pretend to run a small fleet of temperature sensors. Normal readings sit around 20 C.
Two failure modes make the demo interesting because the *algorithm* flags both, but only
one is a real problem — which is exactly what the AI layer (step 04) is for:

  * disconnect spike  — a single wild reading (~95 C). Benign: the sensor briefly dropped out.
  * overheating run   — many consecutive elevated readings (~34 C). Genuine: real heat.
"""
import random

from instaclustr_sdk import Event

SENSORS = ["sensor-1", "sensor-2", "sensor-3"]
METRIC = "temperature"


def normal_reading(entity: str) -> Event:
    return Event(entity, METRIC, random.gauss(20.0, 0.5))


def baseline(per_sensor: int = 200, fleet=SENSORS):
    """A healthy history for every sensor — establishes each one's normal band."""
    return [normal_reading(s) for s in fleet for _ in range(per_sensor)]


def disconnect_spike(entity: str = "sensor-1") -> Event:
    """One wild sample — looks extreme, but it's just a momentary dropout (benign)."""
    return Event(entity, METRIC, 95.0)


def overheating_run(entity: str = "sensor-2", n: int = 15, temp: float = 34.0):
    """A sustained elevated stretch — a real overheating event (genuine)."""
    return [Event(entity, METRIC, random.gauss(temp, 0.5)) for _ in range(n)]
