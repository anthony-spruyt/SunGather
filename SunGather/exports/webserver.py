"""Webserver export for SunGather — serves HTML, JSON, metrics, and health."""

import json
import logging
import socket
import urllib

from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

from version import __version__  # pylint: disable=import-error


def sanitize_for_log(value):
    """Remove control characters to prevent log injection."""
    return (
        str(value)
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _build_config_rows(items):
    """Build HTML table rows for config display."""
    rows = ""
    for setting, value in items:
        s, v = str(setting), str(value)
        rows += (
            f'<tr><td><label for="{s}">{s}:</label></td>'
            f'<td><input type="text" id="{s}" name="{s}" '
            f'value="{v}"></td>'
            f'<td><input type="checkbox" id="update_{s}" '
            f'name="update_{s}" value="False"></td></tr>'
        )
    return rows


class ExportWebserver(object):
    """Webserver export plugin — serves data and health endpoint."""

    html_body = "Pending Data Retrieval"
    metrics = ""
    last_successful_scrape = None
    inverter_host = None
    inverter_port = 502
    scan_interval = 30

    def __init__(self):
        pass

    def configure(self, config, inverter):
        """Set up the HTTP server and store inverter config."""
        ExportWebserver.scan_interval = (
            inverter.inverter_config['scan_interval']
        )
        ExportWebserver.inverter_host = (
            inverter.client_config.get('host')
        )
        # HTTP mode overrides port to 8082 inside SungrowClient.connect(),
        # so use that for the reachability check instead of the config port.
        if inverter.inverter_config.get('connection') == 'http':
            ExportWebserver.inverter_port = 8082
        else:
            ExportWebserver.inverter_port = (
                inverter.client_config.get('port', 502)
            )
        try:
            self.web_server = HTTPServer(
                ('', config.get('port', 8080)), MyServer
            )
            self.server_thread = Thread(
                target=self.web_server.serve_forever
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            logging.info("Webserver: Configured")
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Webserver: Error during startup")
            return False
        config_body = (
            f"<h3>SunGather v{__version__}</h3></p>"
            "<h4>Configuration changes require a restart "
            "to take effect!</h4>"
            '<form action="/config">'
            "<label>Inverter Settings:</label><br>"
            "<table><tr><th>Option</th><th>Setting</th>"
            "<th>Update?</th></tr>"
        )
        config_body += _build_config_rows(
            inverter.client_config.items()
        )
        config_body += _build_config_rows(
            inverter.inverter_config.items()
        )
        config_body += (
            "</table>Currently ReadOnly, "
            "No save function yet :(</form>"
        )
        ExportWebserver.config = config_body
        return True

    def publish(self, inverter):
        """Update webserver data from a successful scrape."""
        ExportWebserver.last_successful_scrape = datetime.now()
        json_array = {
            "registers": {},
            "client_config": {},
            "inverter_config": {},
        }
        metrics_body = ""
        main_body = (
            f"<h3>SunGather v{__version__}</h3></p>"
            "<h4>Need Help? "
            '<a href="https://github.com/anthony-spruyt/SunGather">'
            "https://github.com/anthony-spruyt/SunGather</a></h4></p>"
        )
        main_body += (
            "<table><th>Address</th>"
            "<tr><th>Register</th><th>Value</th></tr>"
        )
        for register, value in inverter.latest_scrape.items():
            addr = str(inverter.getRegisterAddress(register))
            unit = str(inverter.getRegisterUnit(register))
            main_body += (
                f"<tr><td>{addr}</td>"
                f"<td>{register}</td>"
                f"<td>{value} {unit}</td></tr>"
            )
            metrics_body += (
                f'{register}{{address="{addr}", '
                f'unit="{unit}"}} {value}\n'
            )
            json_array["registers"][addr] = {
                "register": str(register),
                "value": str(value),
                "unit": unit,
            }
        total = len(inverter.latest_scrape)
        main_body += f"</table><p>Total {total} registers"

        main_body += (
            "</p></p><table>"
            "<tr><th>Configuration</th><th>Value</th></tr>"
        )
        for setting, value in inverter.client_config.items():
            s, v = str(setting), str(value)
            main_body += f"<tr><td>{s}</td><td>{v}</td></tr>"
            json_array["client_config"][s] = v
        for setting, value in inverter.inverter_config.items():
            s, v = str(setting), str(value)
            main_body += f"<tr><td>{s}</td><td>{v}</td></tr>"
            json_array["inverter_config"][s] = v
        main_body += "</table></p>"

        ExportWebserver.main = main_body
        ExportWebserver.metrics = metrics_body
        ExportWebserver.json = json.dumps(json_array)
        return True


# Backwards-compatible alias used by sungather.py dynamic import
export_webserver = ExportWebserver


def check_inverter_reachable(host, port, timeout=2):
    """TCP connect to the inverter's Modbus/HTTP port.

    Returns True if the port accepts a connection, indicating the
    inverter is powered on. For HTTP-mode inverters this checks
    port 8082, not the Modbus port.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _serve_health(handler):
    """Handle GET /health — inverter reachability + data freshness."""
    threshold = ExportWebserver.scan_interval * 3
    host = ExportWebserver.inverter_host
    port = ExportWebserver.inverter_port
    last = ExportWebserver.last_successful_scrape

    if not host:
        logging.warning("Health check: inverter host not configured")
        status = 503
        body = {
            "status": "error",
            "detail": "not_configured",
            "inverter_reachable": False,
            "last_scrape_age_seconds": None,
            "threshold_seconds": threshold,
        }
    elif not check_inverter_reachable(host, port):
        status = 200
        body = {
            "status": "ok",
            "detail": "inverter_offline",
            "inverter_reachable": False,
            "last_scrape_age_seconds": None,
            "threshold_seconds": threshold,
        }
    elif last is not None:
        age = (datetime.now() - last).total_seconds()
        if age < threshold:
            status = 200
            body = {
                "status": "ok",
                "detail": "fresh",
                "inverter_reachable": True,
                "last_scrape_age_seconds": round(age, 1),
                "threshold_seconds": threshold,
            }
        else:
            status = 503
            body = {
                "status": "stale",
                "detail": "scrape_failing",
                "inverter_reachable": True,
                "last_scrape_age_seconds": round(age, 1),
                "threshold_seconds": threshold,
            }
    else:
        status = 503
        body = {
            "status": "stale",
            "detail": "connected_not_scraping",
            "inverter_reachable": True,
            "last_scrape_age_seconds": None,
            "threshold_seconds": threshold,
        }

    handler.send_response(status)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(body).encode("utf-8"))


_CSS = (
    '<style media = "all"> '
    "body { background-color: black; color: white; } "
    "@media screen and (prefers-color-scheme: light) "
    "{ body { background-color: white; color: black; } } "
    "</style>"
)


class MyServer(BaseHTTPRequestHandler):
    """HTTP request handler for SunGather web interface."""

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle GET requests."""
        if self.path == '/health':
            _serve_health(self)
            return
        if self.path.startswith('/metrics'):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(
                ExportWebserver.metrics.encode("utf-8")
            )
        elif self.path.startswith('/config'):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                ExportWebserver.config.encode("utf-8")
            )
            parsed_data = parse_qs(urlparse(self.path).query)
            logging.info(sanitize_for_log(parsed_data))
        elif self.path.startswith('/json'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                ExportWebserver.json.encode("utf-8")
            )
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            parts = [
                "<html><head><title>SunGather</title>",
                "<meta charset='UTF-8'>"
                "<meta http-equiv='refresh' content='15'>",
                _CSS,
                "</head><body>",
                ExportWebserver.main,
                "</table></body></html>",
            ]
            for part in parts:
                self.wfile.write(part.encode("utf-8"))

    def do_POST(self):  # pylint: disable=invalid-name
        """Handle POST requests."""
        length = int(self.headers['Content-Length'])
        post_data = urllib.parse.parse_qs(
            self.rfile.read(length).decode('utf-8')
        )
        logging.info(sanitize_for_log(post_data))
        self.wfile.write(json.dumps(post_data).encode("utf-8"))

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        """Suppress default HTTP logging."""
