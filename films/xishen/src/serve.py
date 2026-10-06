"""A local-only screening server with byte ranges for reliable movie seeking."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class ScreeningHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        self.byte_range = None
        header = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not header or not path.is_file():
            return super().send_head()
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
        fh = path.open("rb")
        size = path.stat().st_size
        start, end = 0, size - 1
        if match and (match[1] or match[2]):
            if match[1]:
                start = int(match[1])
                end = min(int(match[2]), end) if match[2] else end
            else:
                suffix = int(match[2])
                start = max(0, size - suffix)
        else:
            start = size
        if start >= size or start > end:
            fh.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        self.byte_range = (start, end)
        self.send_response(206)
        self.send_header("Content-type", self.guess_type(str(path)))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        fh.seek(start)
        return fh

    def copyfile(self, source, outputfile):
        try:
            if self.byte_range is None:
                return super().copyfile(source, outputfile)
            remaining = self.byte_range[1] - self.byte_range[0] + 1
            while remaining:
                block = source.read(min(remaining, 256 * 1024))
                if not block:
                    break
                outputfile.write(block)
                remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            # Browsers cancel the previous range when the viewer seeks again.
            pass

    def log_message(self, fmt, *args):
        if not args or str(args[1] if len(args)>1 else "") not in ("200", "206", "304"):
            super().log_message(fmt, *args)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args(args)
    handler = partial(ScreeningHandler, directory=str(ROOT))
    with ThreadingHTTPServer(("127.0.0.1", options.port), handler) as server:
        print(f"Watch: http://127.0.0.1:{server.server_port}/watch.html", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
