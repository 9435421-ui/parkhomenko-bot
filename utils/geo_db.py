import json
import os

class GeoJKDatabase:
    def __init__(self, file_path="knowledge_base/geo_jk.json"):
        self.file_path = file_path
        self.data = self._load_data()

    def _load_data(self):
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def get_jk_info(self, jk_name):
        # Поиск по точному совпадению или частичному
        for name, info in self.data.items():
            if jk_name.lower() in name.lower():
                return info
        return None

geo_db = GeoJKDatabase()
