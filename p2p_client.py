#!/usr/bin/env python3
import argparse
import base64
import json
import socket
import sys
from pathlib import Path

from tqdm import tqdm

# Import local modules
from file_share.crypto import Crypto
from file_share.resume_manager import ResumeManager


class P2PClient:
    def __init__(self, download_dir='./downloads', key=None):
        if not key:
            raise ValueError("Encryption key is required")

        self.crypto = Crypto(key)
        self.key = key
        self.resume_manager = ResumeManager()

        # Create download directory
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        print(f"📁 Download directory: {self.download_dir.absolute()}")

    def create_socket(self, proxy_config=None):
        """Create socket with optional proxy support"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # Reduced timeout for faster feedback
        return sock

    def send_request(self, host, port, request, proxy_config=None):
        """Send a request to the server and get response"""
        print(f"🔗 Connecting to {host}:{port}...")
        try:
            # Connect to server
            sock = self.create_socket(proxy_config)
            sock.connect((host, port))
            print(f"✅ Connected to {host}:{port}")

            # Send request
            request_json = json.dumps(request)
            print(f"📤 Sending request: {request['command']}")
            sock.send(request_json.encode('utf-8'))

            # Receive response
            response_data = b''
            while True:
                try:
                    chunk = sock.recv(8192)
                    if not chunk:
                        break
                    response_data += chunk
                except socket.timeout:
                    print("⏰ Socket timeout during receive")
                    break

            sock.close()

            if not response_data:
                print("❌ No response data received")
                return None

            # Parse response
            try:
                response = json.loads(response_data.decode('utf-8'))
                print(f"📥 Received response: {response.get('status', 'unknown')}")
                return response
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"📦 Raw response: {response_data[:200]}...")  # First 200 chars
                return None

        except socket.timeout:
            print(f"⏰ Connection timeout to {host}:{port}")
            return None
        except ConnectionRefusedError:
            print(f"❌ Connection refused by {host}:{port}. Is the node running?")
            return None
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None

    def get_file_info(self, host, port, filename, proxy_config=None):
        """Get file information from server"""
        request = {'command': 'get_file_info', 'filename': filename}
        return self.send_request(host, port, request, proxy_config)

    def request_file_list(self, host, port, proxy_config=None):
        """Get list of available files from server"""
        request = {'command': 'list_files'}
        return self.send_request(host, port, request, proxy_config)

    def download_file_chunked(self, host, port, filename, save_path=None, resume=True, proxy_config=None):
        """Download a file using chunked approach (compatible with P2P node)"""
        if save_path is None:
            save_path = self.download_dir / filename

        print(f"⬇️  Downloading '{filename}' from {host}:{port}")

        # Get file information first
        file_info = self.get_file_info(host, port, filename, proxy_config)
        if not file_info or file_info.get('status') != 'success':
            error_msg = file_info.get('message', 'Unknown error') if file_info else 'No response'
            print(f"❌ Error getting file info: {error_msg}")
            return None

        file_size = file_info['file_info']['size']
        file_hash = file_info['file_info']['hash']

        print(f"📊 File size: {file_size:,} bytes")

        # Setup download paths
        temp_path = Path(str(save_path) + '.part')
        final_path = Path(save_path)

        # Handle resume
        existing_size = 0
        if resume and temp_path.exists():
            existing_size = temp_path.stat().st_size
            if existing_size < file_size:
                print(f"🔄 Resuming download from {existing_size:,} bytes")
            else:
                print("❌ Partial file larger than server file, starting over")
                temp_path.unlink()
                existing_size = 0

        # Download file in chunks
        chunk_size = 1024 * 1024  # 1MB chunks
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        try:
            with open(final_path, 'wb' if existing_size == 0 else 'ab') as f:
                with tqdm(total=file_size, unit='B', unit_scale=True,
                          desc=f"Downloading {filename}", initial=existing_size) as pbar:

                    start_chunk = existing_size // chunk_size

                    for chunk_index in range(start_chunk, total_chunks):
                        # Request chunk from server
                        request = {
                            'command': 'download_chunk',
                            'filename': filename,
                            'chunk_index': chunk_index
                        }

                        response = self.send_request(host, port, request, proxy_config)

                        if not response or response.get('status') != 'success':
                            error_msg = response.get('message', 'Unknown error') if response else 'No response'
                            print(f"\n❌ Error downloading chunk {chunk_index}: {error_msg}")
                            return None

                        # Decrypt and write chunk
                        encrypted_chunk = base64.b64decode(response['chunk_data'])
                        chunk_data = self.crypto.decrypt(encrypted_chunk)

                        f.write(chunk_data)
                        f.flush()

                        pbar.update(len(chunk_data))

                        # Update progress every chunk
                        current_pos = existing_size + (chunk_index - start_chunk + 1) * len(chunk_data)
                        pbar.set_postfix_str(f"Chunk {chunk_index + 1}/{total_chunks}")

            # Verify file size
            final_size = final_path.stat().st_size
            if final_size == file_size:
                print(f"✅ Download completed: {final_path} ({final_size:,} bytes)")
                return str(final_path)
            else:
                print(f"⚠️  Download completed but size mismatch: {final_size:,} vs {file_size:,} bytes")
                return str(final_path)

        except Exception as e:
            print(f"❌ Download failed: {e}")
            # Don't delete partial file for resume capability
            return None

    def list_incomplete_downloads(self):
        """List all incomplete downloads that can be resumed"""
        incomplete = self.resume_manager.list_incomplete_downloads()
        if incomplete:
            print("\n📋 Incomplete downloads that can be resumed:")
            print("=" * 60)
            for filename, info in incomplete.items():
                downloaded = info.get('downloaded', 0)
                total_size = info.get('total_size', 0)
                progress = (downloaded / total_size * 100) if total_size > 0 else 0
                status = "🔄" if progress > 0 else "⏸️"
                print(f"  {status} {filename}: {downloaded:,}/{total_size:,} bytes ({progress:.1f}%)")
            print("=" * 60)
        else:
            print("✅ No incomplete downloads found")

        return incomplete

    def cleanup_incomplete_downloads(self):
        """Clean up all incomplete download states and temp files"""
        incomplete = self.resume_manager.list_incomplete_downloads()
        if incomplete:
            print("\n🧹 Cleaning up incomplete downloads:")
            for filename, info in incomplete.items():
                temp_path = Path(info.get('temp_path', ''))
                if temp_path.exists():
                    temp_path.unlink()
                    print(f"  ❌ Removed: {temp_path}")
                self.resume_manager.complete_download(filename)
                print(f"  🗑️  Cleared state: {filename}")
            print("✅ Cleanup completed")
        else:
            print("✅ Nothing to clean up")

    def search_files(self, host, port, query, proxy_config=None):
        """Search for files on the server - client-side implementation"""
        files_response = self.request_file_list(host, port, proxy_config)
        if files_response and files_response.get('status') == 'success':
            files = files_response.get('files', {})
            matches = [filename for filename in files.keys() if query.lower() in filename.lower()]
            return matches
        return []

    def get_node_info(self, host, port, proxy_config=None):
        """Get information about the node"""
        # Try to get basic info from file list
        files_response = self.request_file_list(host, port, proxy_config)
        if files_response and files_response.get('status') == 'success':
            files = files_response.get('files', {})
            return {
                'host': host,
                'port': port,
                'files_count': len(files),
                'supports_resume': True,  # Our node supports resume
                'version': '1.0'
            }
        return {}


def main():
    parser = argparse.ArgumentParser(
        description='P2P File Share Client - Compatible with P2P Node',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List available files
  python p2p_client.py --host 192.168.1.100 --port 8080 --list --key mypassword123

  # Download a file with chunked transfer (recommended)
  python p2p_client.py --host localhost --port 8080 --download file.txt --key mypassword123

  # Download without resume
  python p2p_client.py --host localhost --port 8080 --download file.txt --key mypassword123 --no-resume

  # List incomplete downloads
  python p2p_client.py --list-incomplete --key mypassword123

  # Clean up incomplete downloads
  python p2p_client.py --cleanup --key mypassword123

  # Use custom download directory
  python p2p_client.py --host localhost --port 8080 --list --key mypassword123 --download-dir /home/user/downloads
        '''
    )

    # Connection options
    parser.add_argument('--host', default='localhost', help='Server host address (default: localhost)')
    parser.add_argument('--port', type=int, default=8080, help='Server port (default: 8080)')
    parser.add_argument('--download-dir', default='./downloads', help='Download directory (default: ./downloads)')

    # Proxy options (optional)
    parser.add_argument('--proxy-type', choices=['socks5', 'socks4', 'http'], help='Proxy type')
    parser.add_argument('--proxy-host', help='Proxy host address')
    parser.add_argument('--proxy-port', type=int, help='Proxy port')
    parser.add_argument('--proxy-user', help='Proxy username')
    parser.add_argument('--proxy-pass', help='Proxy password')

    # Encryption (required)
    parser.add_argument('--key', required=True, help='Encryption key (min 8 characters)')

    # Download options
    parser.add_argument('--no-resume', action='store_true', help='Disable resume functionality')

    # Actions (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--list', action='store_true', help='List available files from server')
    action_group.add_argument('--download', help='Download specific file from server')
    action_group.add_argument('--search', help='Search for files on server')
    action_group.add_argument('--info', action='store_true', help='Get server information')
    action_group.add_argument('--list-incomplete', action='store_true', help='List incomplete downloads')
    action_group.add_argument('--cleanup', action='store_true', help='Clean up incomplete downloads')

    args = parser.parse_args()

    # Validate key
    if len(args.key) < 8:
        print("❌ Error: Key must be at least 8 characters long")
        sys.exit(1)

    # Build proxy config if provided
    proxy_config = None
    if args.proxy_type and args.proxy_host and args.proxy_port:
        proxy_config = {
            'proxy_type': args.proxy_type,
            'addr': args.proxy_host,
            'port': args.proxy_port,
            'username': args.proxy_user or '',
            'password': args.proxy_pass or ''
        }
        print(f"🔌 Using {args.proxy_type} proxy: {args.proxy_host}:{args.proxy_port}")

    try:
        client = P2PClient(download_dir=args.download_dir, key=args.key)

        if args.list_incomplete:
            client.list_incomplete_downloads()

        elif args.cleanup:
            client.cleanup_incomplete_downloads()

        elif args.list:
            print(f"📂 Requesting file list from {args.host}:{args.port}")
            response = client.request_file_list(args.host, args.port, proxy_config)
            if response and response.get('status') == 'success':
                files = response.get('files', {})
                if files:
                    print(f"\n📁 Available files ({len(files)}):")
                    print("=" * 60)
                    for filename, info in files.items():
                        size_mb = info['size'] / (1024 * 1024)
                        print(f"  📄 {filename} ({size_mb:.2f} MB) - {info['hash'][:16]}...")
                    print("=" * 60)
                else:
                    print("📭 No files available on server")
            else:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                print(f"❌ Failed to get file list: {error_msg}")

        elif args.download:
            result = client.download_file_chunked(
                args.host,
                args.port,
                args.download,
                resume=not args.no_resume,
                proxy_config=proxy_config
            )
            if not result:
                print("❌ Download failed")
                sys.exit(1)

        elif args.search:
            print(f"🔍 Searching for '{args.search}' on {args.host}:{args.port}")
            matches = client.search_files(args.host, args.port, args.search, proxy_config)
            if matches is not None:
                if matches:
                    print(f"\n🎯 Search results ({len(matches)} matches):")
                    print("=" * 50)
                    for match in matches:
                        print(f"  📄 {match}")
                    print("=" * 50)
                else:
                    print("🔍 No files match your search")
            else:
                print("❌ Search failed")

        elif args.info:
            print(f"ℹ️  Getting node information from {args.host}:{args.port}")
            node_info = client.get_node_info(args.host, args.port, proxy_config)
            if node_info:
                print(f"\n🖥️  Node Information:")
                print(f"  Host: {node_info.get('host', 'Unknown')}")
                print(f"  Port: {node_info.get('port', 'Unknown')}")
                print(f"  Files: {node_info.get('files_count', 0)}")
                print(f"  Version: {node_info.get('version', 'Unknown')}")
                print(f"  Resume Support: {'Yes' if node_info.get('supports_resume') else 'No'}")
            else:
                print("❌ Failed to get node information")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
