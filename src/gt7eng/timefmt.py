from __future__ import annotations


def format_lap_time(milliseconds: int | None) -> str:
    if milliseconds is None or milliseconds < 0:
        return "--:--.---"
    minutes, remainder = divmod(int(milliseconds), 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes}:{seconds:02}.{millis:03}"


def format_spoken_lap_time(milliseconds: int | None) -> str:
    if milliseconds is None or milliseconds < 0:
        return "time unavailable"
    total_seconds = int((milliseconds + 500) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02}"


def format_duration(milliseconds: int | None) -> str:
    if milliseconds is None or milliseconds < 0:
        return "--:--"
    total_seconds = int(milliseconds // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def format_duration_words(milliseconds: int | None) -> str:
    if milliseconds is None or milliseconds < 0:
        return "time unavailable"
    total_seconds = int(round(milliseconds / 1000))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(plural(hours, "hour"))
    if minutes:
        parts.append(plural(minutes, "minute"))
    if not parts and seconds:
        parts.append(plural(seconds, "second"))
    if not parts:
        return "less than 1 second"
    return " ".join(parts)


def format_delta(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "+0.000"
    sign = "+" if milliseconds >= 0 else "-"
    return f"{sign}{abs(milliseconds) / 1000:.3f}"


def format_spoken_delta(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "time unavailable"
    total_seconds = int((abs(milliseconds) + 500) // 1000)
    if total_seconds < 1:
        return "less than 1 second"
    return f"about {plural(total_seconds, 'second')}"


def plural(value: int, unit: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value} {unit}{suffix}"
