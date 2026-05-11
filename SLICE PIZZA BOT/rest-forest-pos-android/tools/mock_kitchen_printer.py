#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock ESC/POS RAW-9100 thermal-printer server.

Slice Pizza — REST FOREST KDS, Sprint 5.

Why this exists
---------------
The real Xprinter XP-Q200 II is still in transit from Авито. Until it lands
on Petr's till, we need *something* on :9100 that:

  * accepts a TCP socket as if it were a print spooler,
  * decodes the ESC/POS bytes we just sent and prints them to stdout
    (with the control commands annotated),
  * optionally simulates a flaky link via --simulate-errors-pct so the
    PrintQueueWorker retry path actually gets exercised.

How the Android app reaches us
------------------------------
- Emulator → host: PrinterConfig.TCP_HOST = "10.0.2.2" routes there.
- Real device on the same Wi-Fi: set TCP_HOST to your laptop's LAN IP
  (e.g. "192.168.1.42"). Don't forget to allow inbound :9100 in macOS
  System Settings → Network → Firewall → "Allow incoming connections".
- adb-reverse alternative for USB-tethered devices:
    `adb reverse tcp:9100 tcp:9100`
  then leave TCP_HOST = "127.0.0.1".

Run
---
    python3 tools/mock_kitchen_printer.py
    python3 tools/mock_kitchen_printer.py --simulate-errors-pct 20
    python3 tools/mock_kitchen_printer.py --host 0.0.0.0 --port 9100

Stdlib-only, no pip install.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import functools
import random
import socket
import socketserver
import sys
from typing import List, Tuple

# Force line-buffered stdout so logs from background processes are visible
# even when redirected. Annoying to debug otherwise.
print = functools.partial(print, flush=True)  # type: ignore[assignment]

# Common ESC/POS control codes we want to decode for human-friendly output.
# Reference: Epson ESC/POS Command Reference,
# https://reference.epson-biz.com/modules/ref_escpos/index.php
ESC = 0x1B
GS = 0x1D
DC1 = 0x11
LF = 0x0A

KNOWN_COMMANDS: List[Tuple[bytes, str]] = [
    (b"\x1b\x40", "ESC @  — initialise printer"),
    (b"\x1b\x61\x00", "ESC a 0 — align left"),
    (b"\x1b\x61\x01", "ESC a 1 — align centre"),
    (b"\x1b\x61\x02", "ESC a 2 — align right"),
    (b"\x1b\x45\x01", "ESC E 1 — bold ON"),
    (b"\x1b\x45\x00", "ESC E 0 — bold OFF"),
    (b"\x1b\x2d\x01", "ESC - 1 — underline ON"),
    (b"\x1b\x2d\x00", "ESC - 0 — underline OFF"),
    (b"\x1d\x21", "GS  ! — character size (2 byte arg follows)"),
    (b"\x1d\x56\x00", "GS  V 0 — full cut"),
    (b"\x1d\x56\x01", "GS  V 1 — partial cut"),
    (b"\x1d\x56\x41", "GS  V A — full cut after feed"),
    (b"\x1b\x42", "ESC B — buzzer (2 byte arg follows)"),
    (b"\x1b\x64", "ESC d — print and feed N lines"),
    (b"\x1b\x4a", "ESC J — print and feed N dots"),
    (b"\x1b\x70", "ESC p — drawer kick"),
    (b"\x1b\x74", "ESC t — codepage select"),
]


def _annotate(buf: bytes) -> str:
    """
    Walk the byte stream and emit a human-readable transcript.

    We do a coarse pass — exact byte-for-byte ESC/POS parsing requires a
    proper state machine and we deliberately keep this dependency-free.
    """
    out: List[str] = []
    i = 0
    while i < len(buf):
        # Try to match a known multi-byte command.
        matched = False
        for cmd, label in KNOWN_COMMANDS:
            if buf[i : i + len(cmd)] == cmd:
                out.append(f"┊ [{cmd.hex()}] {label}")
                i += len(cmd)
                matched = True
                break
        if matched:
            continue

        b = buf[i]
        if b == LF:
            out.append("┊ (LF)")
            i += 1
            continue
        if b < 0x20 or b == 0x7F:
            out.append(f"┊ (ctrl 0x{b:02x})")
            i += 1
            continue

        # Greedy run of printable bytes — decode as cp866 first (Russian
        # ESC/POS default), then fall back to utf-8 then latin-1.
        run_end = i
        while run_end < len(buf) and 0x20 <= buf[run_end] < 0x7F or buf[run_end] >= 0x80:
            if buf[run_end] == LF:
                break
            run_end += 1
        chunk = buf[i:run_end]
        for codec in ("utf-8", "cp866", "cp1251", "latin-1"):
            try:
                out.append(f">> {chunk.decode(codec)}")
                break
            except UnicodeDecodeError:
                continue
        else:
            out.append(f">> {chunk!r}")
        i = run_end if run_end > i else i + 1
    return "\n".join(out)


class _Handler(socketserver.BaseRequestHandler):
    server_version = "MockKitchenPrinter/1.0"

    # Populated by main()
    error_pct: int = 0

    def handle(self) -> None:
        peer = self.client_address
        ts = _dt.datetime.now().isoformat(timespec="seconds")
        print()
        print("=" * 64)
        print(f"[{ts}] connection from {peer[0]}:{peer[1]}")

        if self.error_pct and random.randint(1, 100) <= self.error_pct:
            print(f"  ✗ simulating connection drop ({self.error_pct}% chance)")
            # Slam the socket closed to mimic a network printer that died
            # mid-stream — exactly the failure mode the worker should
            # recover from with exponential back-off.
            try:
                self.request.close()
            except OSError:
                pass
            return

        chunks: List[bytes] = []
        self.request.settimeout(2.0)
        try:
            while True:
                data = self.request.recv(4096)
                if not data:
                    break
                chunks.append(data)
        except socket.timeout:
            pass
        finally:
            try:
                self.request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        buf = b"".join(chunks)
        if not buf:
            print("  (empty payload — likely a probe call)")
            return

        print(f"  received {len(buf)} bytes — annotated transcript:")
        print(_annotate(buf))


class _ReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--host", default="0.0.0.0", help="Bind interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9100, help="TCP port (default: 9100)")
    parser.add_argument(
        "--simulate-errors-pct",
        type=int,
        default=0,
        metavar="0-100",
        help="Probability of dropping each incoming connection without "
        "responding — for exercising the worker's retry path.",
    )
    args = parser.parse_args()
    _Handler.error_pct = max(0, min(100, args.simulate_errors_pct))

    print(f"mock_kitchen_printer.py — listening on {args.host}:{args.port}")
    if _Handler.error_pct:
        print(f"  simulating errors at {_Handler.error_pct}%")
    print("  Ctrl-C to quit.")

    try:
        with _ReuseTCP((args.host, args.port), _Handler) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
