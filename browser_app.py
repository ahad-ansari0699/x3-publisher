#!/usr/bin/env python3
from __future__ import annotations

import html
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>X3 Publisher Alpha</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 760px; margin: 70px auto; padding: 0 24px; line-height: 1.45; }
.card { border: 1px solid #ddd; border-radius: 16px; padding: 28px; box-shadow: 0 3px 18px #0001; }
h1 { margin-top: 0; }
input[type=file] { display:block; margin: 24px 0; font-size: 1rem; }
button { font-size: 1rem; padding: 12px 20px; border-radius: 10px; border: 1px solid #aaa; cursor:pointer; }
.note { color:#555; font-size:.93rem; }
</style>
</head>
<body>
<div class="card">
<h1>X3 Publisher Alpha</h1>
<p>Choose a scanned PDF to analyze before OCR and EPUB conversion.</p>
<form method="post" enctype="multipart/form-data">
<input type="file" name="pdf" accept="application/pdf,.pdf" required>
<button type="submit">Analyze PDF</button>
</form>
<p class="note">Uploaded PDFs and analysis reports are saved in your Downloads folder under X3 Publisher Uploads.</p>
</div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def do_POST(self):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self.send_error(400, "Expected file upload")
            return

        import cgi

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype},
        )
        item = form["pdf"]
        if not getattr(item, "filename", ""):
            self.send_error(400, "No file selected")
            return

        uploads = Path.home() / "Downloads" / "X3 Publisher Uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        pdf_path = uploads / Path(item.filename).name
        with pdf_path.open("wb") as destination:
            copy_file(item.file, destination)

        output = pdf_path.with_name(pdf_path.stem + " - X3 Analysis")
        cmd = [
            PYTHON,
            str(ROOT / "x3publisher" / "analyzer.py"),
            str(pdf_path),
            "-o",
            str(output),
        ]

        try:
            subprocess.run(cmd, check=True)
            report = output / "report.html"
            webbrowser.open(report.as_uri())
            response = f"""<!doctype html><html><body style="font-family:-apple-system,sans-serif;max-width:720px;margin:60px auto">
            <h1>Analysis complete</h1>
            <p>The report has been opened in a new browser tab.</p>
            <p><strong>Saved to:</strong><br>{html.escape(str(report))}</p>
            <p><a href="/">Analyze another PDF</a></p>
            </body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))
        except subprocess.CalledProcessError as exc:
            self.send_error(500, f"Analysis failed: {exc}")

    def log_message(self, format, *args):
        pass


def copy_file(source, destination, length=1024 * 1024):
    while chunk := source.read(length):
        destination.write(chunk)


def main():
    server = HTTPServer(("127.0.0.1", 8765), Handler)
    url = "http://127.0.0.1:8765"
    print(f"X3 Publisher is running at {url}")
    print("Keep this Terminal window open while using the app.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
