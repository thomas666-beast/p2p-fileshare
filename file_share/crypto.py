import os
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class Crypto:
    def __init__(self, key=None):
        if key is None:
            raise ValueError("Encryption key is required")

        # Validate key length
        if len(key) < 8:
            raise ValueError("Key must be at least 8 characters long")

        self.raw_key = key

        # Derive a proper Fernet key from the password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'p2p_file_share_salt',
            iterations=100000,
        )
        key_bytes = key.encode() if isinstance(key, str) else key
        key_base64 = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        self.fernet = Fernet(key_base64)

        # Store key hash for verification
        self.key_hash = hashlib.sha256(key.encode()).hexdigest()

    def encrypt(self, data):
        if isinstance(data, str):
            data = data.encode()
        return self.fernet.encrypt(data)

    def decrypt(self, encrypted_data):
        return self.fernet.decrypt(encrypted_data)

    def encrypt_file(self, file_path):
        with open(file_path, 'rb') as f:
            file_data = f.read()

        encrypted_data = self.encrypt(file_data)
        encrypted_path = file_path + '.enc'

        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        return encrypted_path

    def decrypt_file(self, encrypted_path, output_path):
        with open(encrypted_path, 'rb') as f:
            encrypted_data = f.read()

        decrypted_data = self.decrypt(encrypted_data)

        with open(output_path, 'wb') as f:
            f.write(decrypted_data)

        return output_path

    def verify_key(self, test_key):
        """Verify if a key matches the current key"""
        test_hash = hashlib.sha256(test_key.encode()).hexdigest()
        return test_hash == self.key_hash
