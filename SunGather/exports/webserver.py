from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from version import __version__
from urllib.parse import parse_qs, urlparse

import json
import logging
import socket
import urllib


def sanitize_for_log(value):
    """Remove control characters to prevent log injection."""
    return str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

class export_webserver(object):
    html_body = "Pending Data Retrieval"
    metrics = ""
    last_successful_scrape = None
    inverter_host = None
    inverter_port = 502
    scan_interval = 30
    def __init__(self):
        False

    # Configure Webserver
    def configure(self, config, inverter):
        export_webserver.scan_interval = inverter.inverter_config['scan_interval']
        export_webserver.inverter_host = inverter.client_config.get('host')
        # HTTP mode overrides port to 8082 inside SungrowClient.connect(),
        # so use that for the reachability check instead of the config port.
        if inverter.inverter_config.get('connection') == 'http':
            export_webserver.inverter_port = 8082
        else:
            export_webserver.inverter_port = inverter.client_config.get('port', 502)
        try:
            self.webServer = HTTPServer(('', config.get('port',8080)), MyServer)
            self.t = Thread(target=self.webServer.serve_forever)
            self.t.daemon = True    # Make it a deamon, so if main loop ends the webserver dies
            self.t.start()
            logging.info(f"Webserver: Configured")
        except Exception as err:
            logging.error(f"Webserver: Error: {err}")
            return False
        pending_config = False
        config_body = f"""
            <h3>SunGather v{__version__}</h3></p>
            <h4>Configuration changes require a restart to take effect!</h4>
            <form action="/config">
            <label>Inverter Settings:</label><br>
            <table><tr><th>Option</th><th>Setting</th><th>Update?</th></tr>
            """
        for setting, value in inverter.client_config.items():
            config_body += f'<tr><td><label for="{str(setting)}">{str(setting)}:</label></td>'
            config_body += f'<td><input type="text" id="{str(setting)}" name="{str(setting)}" value="{str(value)}"></td>'
            config_body += f'<td><input type="checkbox" id="update_{str(setting)}" name="update_{str(setting)}" value="False"></td></tr>'
        for setting, value in inverter.inverter_config.items():
            config_body += f'<tr><td><label for="{str(setting)}">{str(setting)}:</label></td>'
            config_body += f'<td><input type="text" id="{str(setting)}" name="{str(setting)}" value="{str(value)}"></td>'
            config_body += f'<td><input type="checkbox" id="update_{str(setting)}" name="update_{str(setting)}" value="False"></td></tr>'
        #config_body += f'</table><input type="submit" value="Submit"></form>'
        config_body += f'</table>Currently ReadOnly, No save function yet :(</form>'
        export_webserver.config = config_body

        return True

    def publish(self, inverter):
        export_webserver.last_successful_scrape = datetime.now()
        json_array={"registers":{}, "client_config":{}, "inverter_config":{}}
        metrics_body = ""
        main_body = f"""
            <h3>SunGather v{__version__}</h3></p>
            <h4>Need Help? <a href='https://github.com/anthony-spruyt/SunGather'>https://github.com/anthony-spruyt/SunGather</a></h4></p>
            """
        main_body += "<table><th>Address</th><tr><th>Register</th><th>Value</th></tr>"
        for register, value in inverter.latest_scrape.items():
            main_body += f"<tr><td>{str(inverter.getRegisterAddress(register))}</td><td>{str(register)}</td><td>{str(value)} {str(inverter.getRegisterUnit(register))}</td></tr>"
            metrics_body += f"{str(register)}{{address=\"{str(inverter.getRegisterAddress(register))}\", unit=\"{str(inverter.getRegisterUnit(register))}\"}} {str(value)}\n"
            json_array["registers"][str(inverter.getRegisterAddress(register))]={"register": str(register), "value":str(value), "unit": str(inverter.getRegisterUnit(register))}
        main_body += f"</table><p>Total {len(inverter.latest_scrape)} registers"

        main_body += "</p></p><table><tr><th>Configuration</th><th>Value</th></tr>"
        for setting, value in inverter.client_config.items():
            main_body += f"<tr><td>{str(setting)}</td><td>{str(value)}</td></tr>"
            json_array["client_config"][str(setting)]=str(value)
        for setting, value in inverter.inverter_config.items():
            main_body += f"<tr><td>{str(setting)}</td><td>{str(value)}</td></tr>"
            json_array["inverter_config"][str(setting)]=str(value)
        main_body += f"</table></p>"

        export_webserver.main = main_body
        export_webserver.metrics = metrics_body
        export_webserver.json = json.dumps(json_array)
        return True

def check_inverter_reachable(host, port, timeout=2):
    """TCP connect to the inverter's Modbus/HTTP port. Returns True if the
    port accepts a connection, indicating the inverter is powered on.
    Note: for HTTP-mode inverters this checks port 8082, not the Modbus port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            threshold = export_webserver.scan_interval * 3
            host = export_webserver.inverter_host
            port = export_webserver.inverter_port
            last = export_webserver.last_successful_scrape

            if not host:
                # configure() was never called or host is missing
                logging.warning("Health check: inverter host not configured")
                status = 503
                body = {"status": "error", "detail": "not_configured",
                        "inverter_reachable": False,
                        "last_scrape_age_seconds": None,
                        "threshold_seconds": threshold}
                self.send_response(status)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps(body), "utf-8"))
                return

            # Check if inverter is reachable right now
            reachable = check_inverter_reachable(host, port)

            if not reachable:
                # Inverter is off (night) or unreachable — that's fine
                status = 200
                body = {"status": "ok", "detail": "inverter_offline",
                        "inverter_reachable": False,
                        "last_scrape_age_seconds": None,
                        "threshold_seconds": threshold}
            elif last is not None:
                age = (datetime.now() - last).total_seconds()
                if age < threshold:
                    status = 200
                    body = {"status": "ok", "detail": "fresh",
                            "inverter_reachable": True,
                            "last_scrape_age_seconds": round(age, 1),
                            "threshold_seconds": threshold}
                else:
                    # Inverter is on but data is stale — something is wrong
                    status = 503
                    body = {"status": "stale", "detail": "scrape_failing",
                            "inverter_reachable": True,
                            "last_scrape_age_seconds": round(age, 1),
                            "threshold_seconds": threshold}
            else:
                # Inverter is reachable but we've never scraped successfully
                status = 503
                body = {"status": "stale", "detail": "connected_not_scraping",
                        "inverter_reachable": True,
                        "last_scrape_age_seconds": None,
                        "threshold_seconds": threshold}
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(body), "utf-8"))
            return
        if self.path.startswith('/metrics'):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.metrics, "utf-8"))
        elif self.path.startswith('/config'):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.config, "utf-8"))
            parsed_data = parse_qs(urlparse(self.path).query)
            logging.info(sanitize_for_log(parsed_data))
        elif self.path.startswith('/json'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.json, "utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>SunGather</title>", "utf-8"))
            self.wfile.write(bytes("<meta charset='UTF-8'><meta http-equiv='refresh' content='15'>", "utf-8"))
            self.wfile.write(bytes('<style media = "all"> body { background-color: black; color: white; } @media screen and (prefers-color-scheme: light) { body { background-color: white; color: black; } } </style>', "utf-8"))
            self.wfile.write(bytes("</head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes(export_webserver.main, "utf-8"))
            self.wfile.write(bytes("</table>", "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        post_data = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
        logging.info(sanitize_for_log(post_data))
        self.wfile.write(json.dumps(post_data).encode("utf-8"))

    def log_message(self, format, *args):
        pass
