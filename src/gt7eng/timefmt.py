from __future__ import annotations


def format_lap_time(milliseconds: int | None) -> str:
    if milliseconds is None or milliseconds < 0:
        return "--:--.---"
    minutes, remainder = divmod(int(milliseconds), 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes}:{seconds:02}.{millis:03}"


def format_delta(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "+0.000"
    sign = "+" if milliseconds >= 0 else "-"
    return f"{sign}{abs(milliseconds) / 1000:.3f}"


def plural(value: int, unit: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value} {unit}{suffix}"
