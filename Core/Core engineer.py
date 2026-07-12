import json
import os

class ArbiEngine:
    def __init__(self, config_path='data/mapping.json'):
        self.config_path = config_path
        self.data = self._load_data()

    def _load_data(self):
        # تحميل البيانات من ملف الـ JSON
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file {self.config_path} not found.")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def convert(self, text, mode='arabic_to_musnad'):
        """تحويل النص بناءً على النمط المختار"""
        mapping = self.data.get(mode, {})
        result = [mapping.get(char, char) for char in text]
        return "".join(result)
