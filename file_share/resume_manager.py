import json
import time
from pathlib import Path
from typing import Dict, Optional


class ResumeManager:
    def __init__(self, state_file: str = "download_state.json"):
        self.state_file = Path(state_file)
        self.download_states: Dict[str, Dict] = self._load_states()

    def _load_states(self) -> Dict:
        """Load download states from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    states = json.load(f)
                    # Filter out old entries (older than 7 days)
                    current_time = time.time()
                    valid_states = {}
                    for filename, state in states.items():
                        if current_time - state.get('timestamp', 0) < 7 * 24 * 60 * 60:  # 7 days
                            valid_states[filename] = state

                    # Save cleaned states
                    if len(valid_states) != len(states):
                        self.download_states = valid_states
                        self.save_states()

                    return valid_states
            except Exception as e:
                print(f"⚠️  Error loading download states: {e}")
                return {}
        return {}

    def save_states(self):
        """Save download states to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.download_states, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving download states: {e}")

    def register_download(self, filename: str, total_size: int, temp_path: str):
        """Register a new download"""
        self.download_states[filename] = {
            'total_size': total_size,
            'downloaded': 0,
            'temp_path': temp_path,
            'active': True,
            'timestamp': time.time(),
            'started': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_states()

    def update_progress(self, filename: str, downloaded: int):
        """Update download progress"""
        if filename in self.download_states:
            self.download_states[filename]['downloaded'] = downloaded
            self.download_states[filename]['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Only save to disk every 1MB to reduce I/O
            if downloaded % (1024 * 1024) == 0:
                self.save_states()

    def complete_download(self, filename: str):
        """Mark download as complete and remove from state"""
        if filename in self.download_states:
            del self.download_states[filename]
            self.save_states()

    def get_resume_info(self, filename: str) -> Optional[Dict]:
        """Get resume information for a file"""
        state = self.download_states.get(filename)
        if state and state.get('active', False):
            return state
        return None

    def list_incomplete_downloads(self) -> Dict:
        """List all incomplete downloads"""
        return {k: v for k, v in self.download_states.items() if v.get('active', False)}
