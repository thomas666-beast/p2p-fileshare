#!/usr/bin/env python3
import json
import getpass
from pathlib import Path


def create_secure_config():
    config_path = Path("config.json")

    if config_path.exists():
        print("⚠ config.json already exists!")
        response = input("Overwrite? (y/N): ").lower()
        if response != 'y':
            print("Cancelled.")
            return

    print("\n🔐 P2P File Share Configuration Setup")
    print("=" * 40)

    # Get encryption key
    while True:
        key = getpass.getpass("Enter encryption key (min 8 characters): ")
        if len(key) < 8:
            print("❌ Key must be at least 8 characters!")
            continue

        key_confirm = getpass.getpass("Confirm encryption key: ")
        if key != key_confirm:
            print("❌ Keys don't match!")
            continue
        break

    # Get node settings
    host = input("Node host [localhost]: ") or "localhost"
    port = input("Node port [8080]: ") or "8080"
    share_dir = input("Share directory [./shared]: ") or "./shared"

    # Create config - only node section
    config = {
        "node": {
            "host": host,
            "port": int(port),
            "share_dir": share_dir,
            "key": key,
            "max_connections": 10
        }
    }

    # Save config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✅ Configuration saved to {config_path}")
        print("\n🚀 You can now start the node:")
        print(f"   python p2p_node.py --config {config_path}")
    except Exception as e:
        print(f"❌ Error saving config: {e}")


if __name__ == '__main__':
    create_secure_config()
