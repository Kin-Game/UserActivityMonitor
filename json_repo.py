import os
from datetime import datetime
from core.utils import load_json, save_json


class JSONRepository:
    def __init__(self, base_path="storage/raw"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _file(self) -> str:
        date = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.base_path, f"{date}.json")

    def save_session(self, session: dict):
        file = self._file()
        data = load_json(file)
        data.append(session)
        save_json(file, data)

    def get_today_sessions(self) -> list[dict]:
  
        file = self._file()
        return load_json(file)
