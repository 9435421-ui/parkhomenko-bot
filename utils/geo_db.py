"""
Справочник ЖК Москвы с техническими особенностями
"""
import json
import os

class GeoDatabase:
    def __init__(self, data_path: str = "knowledge_base/geo_jk.json"):
        self.data_path = data_path
        self.jk_data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "JK_Luch": {
                "name": "ЖК Лучи",
                "series": "П-44Т",
                "features": "Панельные дома, есть ограничения по сносу несущих стен.",
                "rules": "Запрещено объединение лоджий без теплового контура."
            },
            "JK_Symbol": {
                "name": "ЖК Символ",
                "series": "Монолит",
                "features": "Монолитно-каркасные дома, свободная планировка.",
                "rules": "Требуется проект при переносе мокрых зон."
            }
        }

    def get_jk_info(self, source: str):
        return self.jk_data.get(source)

    def list_jks(self):
        return [
            {"code": code, "name": info["name"]}
            for code, info in self.jk_data.items()
        ]

    def add_jk(self, code: str, name: str):
        self.jk_data[code] = {
            "name": name,
            "series": "Не указано",
            "features": "Информация уточняется.",
            "rules": "Уточняйте у эксперта."
        }
        # В MVP просто обновляем в памяти, для персистентности нужно сохранять в файл
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.jk_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения гео-базы: {e}")

# Singleton instance
geo_db = GeoDatabase()
