import os
import json
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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
# Ensure absolute path for security
UPLOAD_DIR = os.path.abspath(config.get('upload_dir', 'uploads'))

os.makedirs(UPLOAD_DIR, exist_ok=True)

class FileServer(SimpleHTTPRequestHandler):
    def get_safe_path(self, filename):
        """
        Safely join the upload directory and the filename.
        Prevents directory traversal attacks (e.g. ../../etc/passwd).
        """
        # Decode URL encoding
        filename = unquote(filename)
        # Remove leading/trailing path separators just in case
        filename = filename.strip(os.path.sep)
        # Join path
        target_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
        # Verify the normalized final path is still inside UPLOAD_DIR
        if os.path.commonpath([UPLOAD_DIR, target_path]) != UPLOAD_DIR:
            return None
        return target_path

    def do_GET(self):
        # 1. Serve Index Page
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

        # 2. Serve Static Files (CSS)
        elif self.path.startswith('/static/'):
            # Basic static file serving logic
            file_path = os.path.join(os.path.dirname(__file__), self.path.lstrip('/'))
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                # Static assets like CSS still need correct MIME types for the UI to work
                if file_path.endswith('.css'):
                    self.send_header("Content-type", "text/css")
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Static file not found")
                return

        # 3. API: List Files
        elif self.path.startswith('/list'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            try:
                files = os.listdir(UPLOAD_DIR)
                # Sort files by modification time (newest first)
                files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)), reverse=True)
                
                file_list = []
                for f in files:
                    # Basic check to avoid system files if needed
                    if not f.startswith('.'):
                        file_list.append({
                            'encoded_name': f, # Keep original for URL
                            'name': f          # Display name
                        })
                self.wfile.write(json.dumps(file_list).encode())
            except Exception as e:
                # Return empty list on error
                self.wfile.write(json.dumps([]).encode())
            return

        # 4. API: File Details
        elif self.path.startswith('/details/'):
            filename_part = self.path[len('/details/'):]
            filepath = self.get_safe_path(filename_part)

            if filepath and os.path.exists(filepath):
                file_stats = os.stat(filepath)
                details = {
                    "name": os.path.basename(filepath),
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

        # 5. Download File (UPDATED: Force Download)
        else:
            requested_file = self.path.lstrip('/')
            filepath = self.get_safe_path(requested_file)

            if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
                # FORCE DOWNLOAD SECURITY: 
                # Always use application/octet-stream for user-uploaded content.
                # This prevents browsers from interpreting files (e.g., executing HTML/JS/SVG).
                mime_type = 'application/octet-stream'

                file_size = os.path.getsize(filepath)

                self.send_response(200)
                self.send_header("Content-type", mime_type)
                self.send_header("Content-Length", file_size)
                # Force 'attachment' to ensure download dialog appears
                self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(filepath)}"')
                self.end_headers()
                
                # Stream file in chunks
                with open(filepath, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            else:
                self.send_error(404, "File not found")

    def do_DELETE(self):
        if not self.path.startswith('/delete/'):
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": "Invalid delete endpoint"}).encode())
            return

        filename = unquote(self.path[len('/delete/'):])
        filepath = self.get_safe_path(filename)

        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f'File deleted'}).encode())
            except Exception as e:
                self.send_error(500, f"Error deleting file: {str(e)}")
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": "File not found"}).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
        except (TypeError, ValueError):
            self.send_error(400, "Missing Content-Length")
            return

        filename = self.headers.get('Filename')
        if not filename:
             self.send_error(400, "Missing Filename header")
             return
        
        filename = unquote(filename)
        filepath = self.get_safe_path(filename)

        if not filepath:
            self.send_error(403, "Invalid filename or path")
            return

        try:
            with open(filepath, 'wb') as f:
                remaining = content_length
                chunk_size = 8192
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, chunk_size))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": f'File {os.path.basename(filepath)} uploaded'}).encode())
        except Exception as e:
            print(f"Upload error: {e}")
            self.send_error(500, "Server error during upload")

def run_server():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, FileServer)
    print(f'🚀 FileFlux Server running on http://localhost:{PORT}')
    print(f'📂 Upload Directory: {UPLOAD_DIR}')
    print('Press Ctrl+C to stop.')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
