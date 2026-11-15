#!/usr/bin/env python3
"""Виртуальный принтер этикеток для опытов с процессами Linux."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import signal
import sys
import time


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def interval_value(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("интервал должен быть конечным числом не меньше нуля")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("значение должно быть целым числом не меньше нуля")
    return number


def print_labels(args: argparse.Namespace) -> int:
    stop_signal: int | None = None
    report_requested = False

    # Handlers only record requests. File operations and output happen in the main loop.
    def request_stop(signum, _frame):
        nonlocal stop_signal
        stop_signal = signum

    def request_report(_signum, _frame):
        nonlocal report_requested
        report_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGUSR1, request_report)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Каталог {output} уже содержит файлы. Выберите новый каталог для нового запуска.")

    pid = os.getpid()
    started_at = timestamp()
    started = time.monotonic()
    cpu_started = time.process_time()
    printed = 0
    lock = output / "printing.lock"
    # Exclusive creation prevents two printers from claiming the same empty directory.
    with lock.open("x", encoding="utf-8") as file:
        json.dump({"name": args.name, "pid": pid, "started_at": started_at}, file, indent=2)
        file.write("\n")

    def log(message: str) -> None:
        print(f"{datetime.now().astimezone():%H:%M:%S} [{args.name}] PID={pid} | {message}", flush=True)

    def statistics() -> dict:
        return {
            "name": args.name,
            "pid": pid,
            "started_at": started_at,
            "labels_printed": printed,
            "batch_size": args.count,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "cpu_seconds": round(time.process_time() - cpu_started, 3),
        }

    batch = str(args.count) if args.count else "без ограничения"
    log(f"Старт. Каталог: {output}; интервал: {args.interval:g} с; партия: {batch}")
    def report() -> None:
        nonlocal report_requested
        if report_requested:
            report_requested = False
            log(f"Статистика (SIGUSR1): напечатано {printed}; "
                f"время с запуска: {time.monotonic() - started:.1f} с; "
                f"время CPU: {time.process_time() - cpu_started:.1f} с")

    next_label = time.monotonic()
    while stop_signal is None:
        report()
        if time.monotonic() >= next_label:
            # Equal CPU work per label makes competition between printers visible.
            # Small chunks keep TERM and USR1 responsive, even with a low priority.
            checksum = 0
            remaining = args.work
            while remaining and stop_signal is None:
                chunk = min(remaining, 10000)
                for _ in range(chunk):
                    checksum = (checksum * 1664525 + 1013904223) & 0xFFFFFFFF
                remaining -= chunk
                report()
            if stop_signal is not None:
                break
            number = printed + 1
            target = output / f"label_{number:04d}.txt"
            target.write_text(
                f"ЭТИКЕТКА № {number}\nПринтер: {args.name}\nPID: {pid}\nСоздана: {timestamp()}\n"
                f"Контрольное число: {checksum}\n",
                encoding="utf-8",
            )
            printed = number
            log(f"Этикетка № {printed} → {target.name}")
            if args.count and printed >= args.count:
                break
            # After a pause, resume normally instead of catching up with a burst of files.
            next_label = time.monotonic() + args.interval
        time.sleep(min(0.1, max(0, next_label - time.monotonic())))

    reason = signal.Signals(stop_signal).name if stop_signal else "batch_complete"
    summary = {**statistics(), "finished_at": timestamp(), "reason": reason}
    temporary = output / "summary.json.tmp"
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "summary.json")
    lock.unlink()
    log(f"Завершён: {reason}. Напечатано: {printed}. Итог: {output / 'summary.json'}")
    return 128 + stop_signal if stop_signal else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="printer",
        description=__doc__,
        epilog="SIGUSR1 выводит статистику; SIGTERM и Ctrl+C сохраняют итог. "
               "Каждый запуск требует отдельного пустого каталога.",
    )
    parser.add_argument("--name", default="printer", help="имя принтера в сообщениях и этикетках (по умолчанию: printer)")
    parser.add_argument("--output", required=True, type=Path, help="новый или пустой каталог для этого запуска")
    parser.add_argument("--interval", type=interval_value, default=2.0, help="интервал между этикетками в секундах (по умолчанию: 2)")
    parser.add_argument("--count", type=nonnegative_int, default=0, help="размер партии; 0 — до завершения сигналом (по умолчанию: 0)")
    parser.add_argument("--work", type=nonnegative_int, default=0, help="число вычислений перед каждой этикеткой (по умолчанию: 0)")
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    args = parser.parse_args()
    try:
        return print_labels(args)
    except (OSError, ValueError) as exc:
        print(f"Ошибка принтера: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
