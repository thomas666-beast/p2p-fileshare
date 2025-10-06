import os
import hashlib
from pathlib import Path


class FileHandler:
    def __init__(self, share_dir):
        # Ensure share_dir is a string with default
        if not share_dir or not isinstance(share_dir, (str, Path)):
            share_dir = './shared'
            print(f"⚠ Using default share directory: {share_dir}")

        self.share_dir = Path(share_dir)

        # Create directory if it doesn't exist
        try:
            self.share_dir.mkdir(exist_ok=True)
            print(f"✓ Share directory: {self.share_dir.absolute()}")
        except Exception as e:
            print(f"✗ Error creating share directory: {e}")
            raise

        self.file_index = {}
        self._scan_files()

    def _scan_files(self):
        self.file_index = {}
        try:
            for file_path in self.share_dir.glob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    self.file_index[file_path.name] = {
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'hash': self._calculate_hash(file_path)
                    }
            print(f"✓ Found {len(self.file_index)} files in share directory")
        except Exception as e:
            print(f"✗ Error scanning files: {e}")

    def _calculate_hash(self, file_path):
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"✗ Error calculating hash for {file_path}: {e}")
            return "error"

    def list_files(self):
        return list(self.file_index.keys())

    def get_file_info(self, filename):
        return self.file_index.get(filename)

    def add_file(self, source_path, filename=None):
        if filename is None:
            filename = Path(source_path).name

        try:
            dest_path = self.share_dir / filename
            import shutil
            shutil.copy2(source_path, dest_path)
            self._scan_files()
            return filename
        except Exception as e:
            print(f"✗ Error adding file {source_path}: {e}")
            return None
