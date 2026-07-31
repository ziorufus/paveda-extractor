import json
import os
import shutil
import sqlite3
from contextlib import closing


class LanguageStore:
    def __init__(self, db_path, excel_folder):
        self.db_path = db_path
        self.excel_folder = excel_folder
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(excel_folder, exist_ok=True)
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS languages (
                    excel_filename TEXT PRIMARY KEY,
                    language_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    contributors TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    @staticmethod
    def _normalize_payload(excel_filename, payload):
        record = dict(payload)
        record["excel_filename"] = excel_filename
        if "ID" not in record or not str(record["ID"]).strip():
            raise ValueError("Language payload must include a non-empty 'ID'")
        if "Name" not in record or not str(record["Name"]).strip():
            raise ValueError("Language payload must include a non-empty 'Name'")
        return record

    def validate_payload(self, excel_filename, payload):
        return self._normalize_payload(excel_filename, payload)

    @staticmethod
    def _row_to_record(row):
        payload = json.loads(row["payload_json"])
        payload["excel_filename"] = row["excel_filename"]
        return payload

    def list_languages(self):
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM languages ORDER BY excel_filename").fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_language(self, excel_filename):
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM languages WHERE excel_filename = ?",
                (excel_filename,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def upsert_language(self, excel_filename, payload):
        record = self._normalize_payload(excel_filename, payload)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO languages (excel_filename, language_id, name, contributors, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(excel_filename) DO UPDATE SET
                    language_id = excluded.language_id,
                    name = excluded.name,
                    contributors = excluded.contributors,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    excel_filename,
                    str(record["ID"]),
                    str(record["Name"]),
                    record.get("contributors"),
                    json.dumps(record, ensure_ascii=False),
                ),
            )
            connection.commit()
        return record

    def create_language(self, excel_filename, payload):
        existing = self.get_language(excel_filename)
        if existing is not None:
            raise ValueError(f"Language '{excel_filename}' already exists")
        return self.upsert_language(excel_filename, payload)

    def update_language(self, current_filename, payload, new_filename=None):
        existing = self.get_language(current_filename)
        if existing is None:
            raise KeyError(current_filename)

        target_filename = new_filename or current_filename
        merged = dict(existing)
        merged.update(payload)
        merged["excel_filename"] = target_filename
        normalized = self._normalize_payload(target_filename, merged)

        if target_filename != current_filename and self.get_language(target_filename) is not None:
            raise ValueError(f"Language '{target_filename}' already exists")

        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM languages WHERE excel_filename = ?", (current_filename,))
            connection.execute(
                """
                INSERT INTO languages (excel_filename, language_id, name, contributors, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    target_filename,
                    str(normalized["ID"]),
                    str(normalized["Name"]),
                    normalized.get("contributors"),
                    json.dumps(normalized, ensure_ascii=False),
                ),
            )
            connection.commit()

        return normalized

    def delete_language(self, excel_filename, delete_excel_file=True):
        existing = self.get_language(excel_filename)
        if existing is None:
            raise KeyError(excel_filename)

        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM languages WHERE excel_filename = ?", (excel_filename,))
            connection.commit()

        if delete_excel_file:
            excel_path = self.excel_path(excel_filename)
            if os.path.exists(excel_path):
                os.remove(excel_path)

    def excel_path(self, excel_filename):
        return os.path.join(self.excel_folder, excel_filename)

    def save_excel_file(self, source_path, excel_filename):
        destination = self.excel_path(excel_filename)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(source_path, destination)
        return destination

    def migrate_from_config(self, config_languages):
        with closing(self._connect()) as connection:
            count = connection.execute("SELECT COUNT(*) FROM languages").fetchone()[0]
        if count > 0:
            return 0

        migrated = 0
        if isinstance(config_languages, dict):
            items = config_languages.items()
        elif isinstance(config_languages, list):
            items = []
            for payload in config_languages:
                if not isinstance(payload, dict):
                    raise ValueError("Languages list entries must be objects")
                excel_filename = payload.get("excel_filename")
                if not excel_filename:
                    raise ValueError("Languages list entries must include 'excel_filename'")
                items.append((excel_filename, payload))
        else:
            raise ValueError("Languages config must be either an object or a list")

        for excel_filename, payload in items:
            self.upsert_language(excel_filename, payload)
            migrated += 1
        return migrated

    def as_mapping(self):
        return {
            record["excel_filename"]: {
                key: value for key, value in record.items() if key != "excel_filename"
            }
            for record in self.list_languages()
        }
