"""Serve this season's public review bundle. Run from any working directory."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1", help="Set the host LAN address to share the review")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    public = Path(__file__).resolve().parents[2] / "docs/preliminary-design"
    if not (public / "index.html").is_file():
        parser.error("Expected docs/preliminary-design/index.html in the season repository")
    handler = partial(SimpleHTTPRequestHandler, directory=str(public))
    with ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f"Review at http://{args.bind}:{server.server_port}/ (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
