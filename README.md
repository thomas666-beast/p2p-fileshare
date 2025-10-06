# P2P File Share
A simple peer-to-peer file sharing system with automatic file discovery and encryption.

## ✨ Features
#### 🔒 Encrypted transfers - All files are encrypted during transfer
#### 📁 Auto file discovery - Automatically detects new files in share directory
#### ⚡ No restart needed - Add files while node is running
#### 🔄 Resume support - Continue interrupted downloads
#### 🚀 Easy to use - Simple command-line interface

## 🚀 Quick Start
### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/p2p-fileshare.git
cd p2p-fileshare

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup
```bash
# Create configuration
python setup_config.py
```

### 3. Start Nod
```bash
# Start the P2P node
python p2p_node.py
```

### 4. Share File
```bash
# Add files to the shared directory
cp your_file.txt shared/
# The node automatically detects new files!
```

### 5. Download Files
```bash
# List available files
python p2p_client.py --host localhost --port 8080 --list --key your_password

# Download a file
python p2p_client.py --host localhost --port 8080 --download file.txt --key your_password
```

## 📁 Project Structure

```text
p2p_fileshare/
├── p2p_node.py          # Main node server
├── p2p_client.py        # Client for file operations
├── setup_config.py      # Configuration setup
├── crypto.py           # Encryption utilities
├── resume_manager.py   # Download resume support
├── config.json         # Configuration (created)
├── shared/             # Share files here (auto-detected)
├── downloads/          # Downloaded files go here
└── README.md
```

## 💻 Commands
### Node Management

```bash
python p2p_node.py --config config.json
```

### Client Operations

```bash
# List available files
python p2p_client.py --host HOST --port PORT --list --key PASSWORD
```

```bash
# Download a file
python p2p_client.py --host HOST --port PORT --download FILENAME --key PASSWORD
```

```bash
# Search for files
python p2p_client.py --host HOST --port PORT --search "query" --key PASSWORD
```

```bash
# List incomplete downloads
python p2p_client.py --list-incomplete --key PASSWORD
```

```bash
# Clean up incomplete downloads
python p2p_client.py --cleanup --key PASSWORD
```

### ⚙️ Configuration
Edit `config.json` to customize:
* Node host and port
* Share directory location
* Encryption key
* Maximum connections

Example configuration:

```json
{
  "node": {
    "host": "localhost",
    "port": 8080,
    "share_dir": "./shared",
    "key": "your_secure_password",
    "max_connections": 10
  }
}
```

### 📋 Requirements
* Python 3.7+
* cryptography
* watchdog
* tqdm

Install all dependencies:

```bash
pip install cryptography watchdog tqdm
```

### 📄 License

MIT License
