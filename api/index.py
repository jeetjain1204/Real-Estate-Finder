"""Vercel serverless entry: HTML notice only.

The Streamlit UI (`streamlit_app.py`) is not ASGI/WSGI and cannot run on Vercel
Functions. Deploy the Streamlit app to Streamlit Cloud, Railway, Render, etc.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>RealEstate Finder</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
    code { background: #f4f4f4; padding: 0.15rem 0.35rem; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>RealEstate Finder</h1>
  <p>This repository is a <strong>Streamlit</strong> app. Vercel Python Functions require an ASGI or WSGI
     callable named <code>app</code>; Streamlit uses its own long-lived server and does not fit that model.</p>
  <p><strong>Run locally:</strong> <code>python -m streamlit run streamlit_app.py</code></p>
  <p><strong>Host the UI:</strong> use
     <a href="https://streamlit.io/cloud">Streamlit Community Cloud</a>,
     Railway, Render, Fly.io, or similar.</p>
</body>
</html>
"""


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_HTML.encode("utf-8"))
