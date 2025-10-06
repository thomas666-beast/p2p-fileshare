#!/usr/bin/env python3
import base64
import hashlib
import json
import socket
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class ShareDirectoryHandler(FileSystemEventHandler):
    def __init__(self, node):
        self.node = node

    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            try:
                if file_path.is_relative_to(self.node.share_dir):
                    print(f"📁 New file detected: {file_path.name}")
                    self.node.update_available_files()
            except ValueError:
                pass

    def on_deleted(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            try:
                if file_path.is_relative_to(self.node.share_dir):
                    print(f"📁 File deleted: {file_path.name}")
                    self.node.update_available_files()
            except ValueError:
                pass

    def on_moved(self, event):
        if not event.is_directory:
            src_path = Path(event.src_path)
            dest_path = Path(event.dest_path)
            try:
                if src_path.is_relative_to(self.node.share_dir):
                    print(f"📁 File moved/renamed: {src_path.name} -> {dest_path.name}")
                    self.node.update_available_files()
            except ValueError:
                pass


class P2PNode:
    def __init__(self, config):
        self.observer = None
        self.host = config['node']['host']
        self.port = config['node']['port']
        self.share_dir = Path(config['node']['share_dir'])
        self.key = config['node']['key']
        self.max_connections = config['node']['max_connections']

        # Create share directory if it doesn't exist
        self.share_dir.mkdir(exist_ok=True)

        # Initialize encryption
        self.fernet = self._derive_key(self.key)

        # Network properties
        self.peers = []
        self.connected_peers = []
        self.server_socket = None
        self.running = False

        # File management
        self.available_files = {}
        self.file_lock = threading.Lock()

        # Scan shared files
        self.scan_shared_files()

        # Start file watcher
        self.start_file_watcher()

        print(f"🚀 P2P Node initialized on {self.host}:{self.port}")
        print(f"📁 Share directory: {self.share_dir}")

    def _derive_key(self, password):
        """Derive a Fernet key from the password"""
        password_bytes = password.encode()
        salt = b'p2p_fileshare_salt_'  # In production, use a random salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return Fernet(key)

    def scan_shared_files(self):
        """Scan and index all files in the share directory"""
        files = {}
        try:
            for file_path in self.share_dir.iterdir():
                if file_path.is_file():
                    file_info = self._get_file_info(file_path)
                    files[file_path.name] = file_info

            with self.file_lock:
                self.available_files = files

            print(f"📊 Found {len(files)} files in share directory")
            return files
        except Exception as e:
            print(f"❌ Error scanning shared files: {e}")
            return {}

    def _get_file_info(self, file_path):
        """Get file information including hash and size"""
        file_hash = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    file_hash.update(chunk)
            return {
                'size': file_path.stat().st_size,
                'hash': file_hash.hexdigest(),
                'path': str(file_path)
            }
        except Exception as e:
            print(f"❌ Error reading file {file_path}: {e}")
            return None

    def start_file_watcher(self):
        """Start monitoring the share directory for changes"""
        try:
            event_handler = ShareDirectoryHandler(self)
            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.share_dir), recursive=True)
            self.observer.start()
            print(f"👀 Monitoring share directory: {self.share_dir}")
        except Exception as e:
            print(f"❌ Error starting file watcher: {e}")
            print("📋 Falling back to polling method...")
            self.start_file_polling()

    def start_file_polling(self, interval=5):
        """Poll the share directory for changes at regular intervals"""
        self.polling_active = True

        def poll_files():
            last_files = set(self.available_files.keys())
            while self.polling_active:
                time.sleep(interval)
                try:
                    current_files = set(self.scan_shared_files().keys())

                    added = current_files - last_files
                    removed = last_files - current_files

                    if added:
                        print(f"✅ New files available: {', '.join(added)}")
                    if removed:
                        print(f"❌ Files removed: {', '.join(removed)}")

                    last_files = current_files
                except Exception as e:
                    print(f"❌ Error in file polling: {e}")

        self.polling_thread = threading.Thread(target=poll_files, daemon=True)
        self.polling_thread.start()
        print(f"🔍 Polling share directory every {interval} seconds")

    def update_available_files(self):
        """Update the list of available files and notify peers"""
        old_files = set(self.available_files.keys())
        new_files = self.scan_shared_files()

        added = set(new_files.keys()) - old_files
        removed = old_files - set(new_files.keys())

        if added:
            print(f"✅ New files available: {', '.join(added)}")
        if removed:
            print(f"❌ Files removed: {', '.join(removed)}")

        # Notify connected peers about file changes
        self.notify_peers_about_changes()

    def notify_peers_about_changes(self):
        """Notify all connected peers about file changes"""
        # This would be implemented when we add peer-to-peer file change notifications
        pass

    def stop_file_watcher(self):
        """Stop the file watcher"""
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        if hasattr(self, 'polling_active'):
            self.polling_active = False

    def handle_client(self, client_socket, address):
        """Handle incoming client connections"""
        try:
            print(f"🔗 Connection from {address}")

            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                try:
                    request = json.loads(data)
                    response = self.process_request(request)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                except json.JSONDecodeError:
                    error_response = {'status': 'error', 'message': 'Invalid JSON'}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))

        except Exception as e:
            print(f"❌ Error handling client {address}: {e}")
        finally:
            client_socket.close()
            print(f"🔒 Connection closed with {address}")

    def process_request(self, request):
        """Process client requests"""
        command = request.get('command')

        if command == 'list_files':
            return self.list_files()
        elif command == 'get_file_info':
            return self.get_file_info(request.get('filename'))
        elif command == 'download_chunk':
            return self.download_chunk(
                request.get('filename'),
                request.get('chunk_index')
            )
        else:
            return {'status': 'error', 'message': 'Unknown command'}

    def list_files(self):
        """Return list of available files"""
        with self.file_lock:
            files_info = {
                name: {'size': info['size'], 'hash': info['hash']}
                for name, info in self.available_files.items()
            }
        return {'status': 'success', 'files': files_info}

    def get_file_info(self, filename):
        """Get information about a specific file"""
        with self.file_lock:
            if filename in self.available_files:
                return {
                    'status': 'success',
                    'file_info': self.available_files[filename]
                }
            else:
                return {'status': 'error', 'message': 'File not found'}

    def download_chunk(self, filename, chunk_index):
        """Serve a chunk of a file to the client"""
        try:
            with self.file_lock:
                if filename not in self.available_files:
                    return {'status': 'error', 'message': 'File not found'}

                file_path = Path(self.available_files[filename]['path'])

            # Read and encrypt the file chunk
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(file_path, 'rb') as f:
                f.seek(chunk_index * chunk_size)
                chunk_data = f.read(chunk_size)

            if chunk_data:
                encrypted_chunk = self.fernet.encrypt(chunk_data)
                return {
                    'status': 'success',
                    'chunk_data': base64.b64encode(encrypted_chunk).decode('utf-8'),
                    'chunk_size': len(chunk_data)
                }
            else:
                return {'status': 'error', 'message': 'Chunk not available'}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def start_server(self):
        """Start the node server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_connections)
            self.running = True

            print(f"🎯 Node listening on {self.host}:{self.port}")
            print("📁 Available files:")
            for filename in self.available_files:
                print(f"   - {filename}")
            print("\n⏹️  Press Ctrl+C to stop the node")

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue

        except Exception as e:
            print(f"❌ Server error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the node"""
        self.running = False
        self.stop_file_watcher()
        if self.server_socket:
            self.server_socket.close()
        print("🛑 Node stopped")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='P2P File Share Node')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file {args.config} not found!")
        print("💡 Run the configuration setup first:")
        print("   python setup_config.py")
        return
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in configuration file {args.config}!")
        return

    node = P2PNode(config)

    try:
        node.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down node...")
        node.stop()


if __name__ == '__main__':
    main()
