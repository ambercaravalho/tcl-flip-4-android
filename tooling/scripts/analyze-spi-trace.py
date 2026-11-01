#!/usr/bin/env python3
"""Summarize a trace produced by capture-spi-trace.sh."""

import argparse
import collections
import re
import statistics

EVENT_RE = re.compile(
    r"\s(?P<timestamp>\d+\.\d+):\s+(?:t440w:)?"
    r"(?P<event>\w+):\s*(?P<fields>.*)$"
)
FIELD_RE = re.compile(r"(\w+)=(0x[0-9a-fA-F]+|-?\d+)")
SPI_DONE_CALLER_RE = re.compile(r"spi_done:\s+\((?P<caller>[\w.]+)")


def fourcc(value: int) -> str:
    return "".join(chr((value >> shift) & 0xFF) for shift in (0, 8, 16, 24))


def milliseconds(values: list[float]) -> str:
    if not values:
        return "n/a"
    converted = [value * 1000 for value in values]
    return (
        f"min={min(converted):.3f} "
        f"median={statistics.median(converted):.3f} "
        f"max={max(converted):.3f} ms"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace")
    args = parser.parse_args()

    events: list[tuple[float, str, dict[str, int]]] = []
    spi_done_callers: collections.Counter[str] = collections.Counter()
    with open(args.trace, encoding="utf-8", errors="replace") as trace:
        for line in trace:
            match = EVENT_RE.search(line)
            if not match:
                continue
            fields = {
                key: int(value, 0)
                for key, value in FIELD_RE.findall(match.group("fields"))
            }
            events.append(
                (float(match.group("timestamp")), match.group("event"), fields)
            )
            caller_match = SPI_DONE_CALLER_RE.search(line)
            if caller_match:
                spi_done_callers[caller_match.group("caller")] += 1

    counts = collections.Counter(event for _, event, _ in events)
    input_transitions: collections.Counter[tuple[int, int]] = collections.Counter()
    updates = collections.Counter()
    windows = collections.Counter()
    te_times: list[float] = []
    kickoff_times: list[float] = []
    spi_starts: list[float] = []
    fence_durations: list[float] = []
    spi_durations: list[float] = []
    te_to_spi: list[float] = []
    kickoff_to_spi: list[float] = []
    last_fence_wait = None
    last_kickoff = None
    last_spi_start = None
    last_te = None

    for timestamp, event, fields in events:
        if event == "update_fb":
            fmt = fields.get("fourcc", 0)
            updates[
                (
                    fields.get("width"),
                    fields.get("height"),
                    fields.get("fb_width"),
                    fields.get("fb_height"),
                    fields.get("pitch"),
                    fourcc(fmt),
                )
            ] += 1
        elif event == "input" and fields.get("type") == 1:
            input_transitions[(fields.get("code", -1), fields.get("value", -1))] += 1
        elif event == "te":
            te_times.append(timestamp)
            last_te = timestamp
        elif event == "fence_wait":
            last_fence_wait = timestamp
        elif event == "fence_wait_done" and last_fence_wait is not None:
            fence_durations.append(timestamp - last_fence_wait)
            last_fence_wait = None
        elif event == "window_reset":
            windows[(fields.get("xres"), fields.get("yres"))] += 1
        elif event == "kickoff":
            kickoff_times.append(timestamp)
            last_kickoff = timestamp
        elif event == "spi_start":
            spi_starts.append(timestamp)
            last_spi_start = timestamp
            if last_te is not None:
                te_to_spi.append(timestamp - last_te)
            if last_kickoff is not None:
                kickoff_to_spi.append(timestamp - last_kickoff)
        elif event == "spi_done" and last_spi_start is not None:
            spi_durations.append(timestamp - last_spi_start)
            last_spi_start = None

    print(f"events: {sum(counts.values())}")
    for event, count in sorted(counts.items()):
        print(f"  {event}: {count}")

    print("update_fb submissions:")
    for key, count in updates.most_common():
        width, height, fb_width, fb_height, pitch, fmt = key
        print(
            f"  {count}x crtc={width}x{height} fb={fb_width}x{fb_height} "
            f"pitch={pitch} fourcc={fmt!r}"
        )
    print("panel window resets:")
    for (xres, yres), count in windows.most_common():
        print(f"  {count}x full-window={xres}x{yres}")
    print("input key transitions:")
    for (code, value), count in sorted(input_transitions.items()):
        print(f"  {count}x code={code} value={value}")
    print("SPI completion callers:")
    for caller, count in spi_done_callers.most_common():
        print(f"  {count}x {caller}")

    te_intervals = [
        current - previous for previous, current in zip(te_times, te_times[1:])
    ]
    kickoff_intervals = [
        current - previous
        for previous, current in zip(kickoff_times, kickoff_times[1:])
    ]
    print(f"Fence wait duration: {milliseconds(fence_durations)}")
    print(f"TE intervals: {milliseconds(te_intervals)}")
    print(f"Kickoff intervals: {milliseconds(kickoff_intervals)}")
    print(f"TE to SPI start: {milliseconds(te_to_spi)}")
    print(f"Kickoff to SPI start: {milliseconds(kickoff_to_spi)}")
    print(f"SPI duration: {milliseconds(spi_durations)}")


if __name__ == "__main__":
    main()
