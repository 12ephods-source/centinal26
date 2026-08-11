from __future__ import annotations

import argparse
import http.server
import os
import socket
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def guess_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Automation OS static site without third-party hosting.")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", default=8080, type=int, help="TCP port.")
    args = parser.parse_args()

    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.ThreadingTCPServer((args.bind, args.port), handler) as server:
        server.daemon_threads = True
        local = f"http://127.0.0.1:{args.port}/"
        print(f"Automation OS website: {local}")
        if args.bind == "0.0.0.0":
            print(f"LAN candidate: http://{guess_lan_ip()}:{args.port}/")
        print("Press Ctrl-C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
