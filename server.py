import os
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

# Load configuration
CONFIG_PATH = 'config.json'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default_config = {'port': 8000, 'upload_dir': 'uploads'}
        with open(CONFIG_PATH, 'w') as f:
            json.dump(default_config, f, indent=4)
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

config = load_config()
PORT = config.get('port', 8000)
UPLOAD_DIR = os.path.abspath(config.get('upload_dir', 'uploads'))

os.makedirs(UPLOAD_DIR, exist_ok=True)

class FileServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/index.html']:
            template_dir = os.path.abspath(os.path.dirname(__file__))
            index_path = os.path.join(template_dir, 'templates', 'index.html')

            if not os.path.exists(index_path):
                self.send_error(404, f"Template file not found: {index_path}")
                return

            with open(index_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
            return

        elif self.path.startswith('/list'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            files = os.listdir(UPLOAD_DIR)
            file_list = []
            for f in files:
                try:
                    decoded_f = unquote(f)
                except:
                    decoded_f = f
                file_list.append({
                    'encoded_name': f,
                    'name': decoded_f
                })

            self.wfile.write(json.dumps(file_list).encode())
            return

        elif self.path.startswith('/details/'):
            filename = unquote(self.headers.get('Filename', 'uploaded_file'))
            filepath = os.path.join(UPLOAD_DIR, filename)

            if os.path.exists(filepath):
                file_stats = os.stat(filepath)
                details = {
                    "name": filename,
                    "size": file_stats.st_size,
                    "last_modified": file_stats.st_mtime
                }
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, **details}).encode())
            else:
                self.send_response(404)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "File not found"}).encode())
            return

        elif os.path.isfile(os.path.join(UPLOAD_DIR, self.path.strip("/"))):
            file_path = os.path.join(UPLOAD_DIR, self.path.strip("/"))
            with open(file_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
            return

        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b'File not found')

    def do_DELETE(self):
        filename = unquote(self.path[len('/delete/'):])
        filepath = os.path.join(UPLOAD_DIR, filename)

        if os.path.exists(filepath):
            os.remove(filepath)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": f'File {filename} deleted'}).encode())
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": "File not found"}).encode())

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        filename = self.headers.get('Filename', 'uploaded_file')
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(self.rfile.read(content_length))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "message": f'File {filename} uploaded'}).encode())

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, FileServer)
    print(f'Serving on port {PORT}, upload dir: {UPLOAD_DIR}')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
