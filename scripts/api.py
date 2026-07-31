import argparse
import io
import json
import os
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

try:
    from .converter_core import DEFAULT_CONFIG_PATH, build_runtime_config, load_config, run_conversion
    from .language_store import LanguageStore
except ImportError:  # pragma: no cover - standalone script compatibility
    from converter_core import DEFAULT_CONFIG_PATH, build_runtime_config, load_config, run_conversion
    from language_store import LanguageStore


class RunConversionRequest(BaseModel):
    set_name: str | None = None
    languages: list[str] = Field(default_factory=list)


def parse_language_payload(raw_payload):
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid language JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Language payload must be a JSON object")
    return payload


def cleanup_temp_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)


def create_app(*, input_folder, excel_folder, db_path, config_path=DEFAULT_CONFIG_PATH):
    base_config = load_config(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = LanguageStore(db_path=db_path, excel_folder=excel_folder)
        store.migrate_from_config(base_config.get("languages", {}))
        app.state.store = store
        app.state.base_config = base_config
        app.state.input_folder = input_folder
        app.state.excel_folder = excel_folder
        yield

    app = FastAPI(title="ValPaL Converter API", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/sets")
    async def list_sets():
        sets = dict(app.state.base_config.get("sets", {}))
        sets["all"] = list(app.state.store.as_mapping().keys())
        return sets

    @app.get("/languages")
    async def list_languages():
        return app.state.store.list_languages()

    @app.get("/languages/{excel_filename}")
    async def get_language(excel_filename: str):
        language = app.state.store.get_language(excel_filename)
        if language is None:
            raise HTTPException(status_code=404, detail="Language not found")
        return language

    @app.post("/languages", status_code=201)
    async def create_language(
        excel_filename: str = Form(...),
        payload_json: str = Form(...),
        excel_file: UploadFile = File(...),
    ):
        payload = parse_language_payload(payload_json)
        try:
            app.state.store.validate_payload(excel_filename, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(await excel_file.read())
        try:
            app.state.store.save_excel_file(temp_path, excel_filename)
            record = app.state.store.create_language(excel_filename, payload)
        except ValueError as exc:
            if os.path.exists(app.state.store.excel_path(excel_filename)):
                os.remove(app.state.store.excel_path(excel_filename))
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return record

    @app.put("/languages/{excel_filename}")
    async def update_language(
        excel_filename: str,
        payload_json: str | None = Form(None),
        new_excel_filename: str | None = Form(None),
        excel_file: UploadFile | None = File(None),
    ):
        existing = app.state.store.get_language(excel_filename)
        if existing is None:
            raise HTTPException(status_code=404, detail="Language not found")

        payload = parse_language_payload(payload_json) if payload_json is not None else {}

        target_filename = new_excel_filename or excel_filename
        try:
            if target_filename != excel_filename and app.state.store.get_language(target_filename) is not None:
                raise ValueError(f"Language '{target_filename}' already exists")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        try:
            merged = dict(existing)
            merged.update(payload)
            app.state.store.validate_payload(target_filename, merged)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        old_excel_path = app.state.store.excel_path(excel_filename)
        target_excel_path = app.state.store.excel_path(target_filename)

        if excel_file is not None:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(await excel_file.read())
            try:
                app.state.store.save_excel_file(temp_path, target_filename)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif target_filename != excel_filename and os.path.exists(old_excel_path):
            os.replace(old_excel_path, target_excel_path)

        try:
            record = app.state.store.update_language(excel_filename, payload, target_filename)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return record

    @app.delete("/languages/{excel_filename}", status_code=204)
    async def delete_language(excel_filename: str):
        try:
            app.state.store.delete_language(excel_filename)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Language not found") from exc
        return None

    @app.post("/convert")
    async def convert(request: RunConversionRequest):
        selected = list(request.languages)
        if request.set_name:
            selected.append(request.set_name)
        if not selected:
            raise HTTPException(status_code=400, detail="Provide at least one language or set_name")

        available_languages = app.state.store.as_mapping()
        resolved_languages = []
        sets = dict(app.state.base_config.get("sets", {}))
        sets["all"] = list(available_languages.keys())
        for item in selected:
            if item in sets:
                resolved_languages.extend(sets[item])
            else:
                resolved_languages.append(item)

        resolved_languages = list(dict.fromkeys(resolved_languages))
        missing = [item for item in resolved_languages if item not in available_languages]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown language files: {', '.join(missing)}",
            )

        temp_dir = tempfile.mkdtemp(prefix="valpal-api-")
        output_dir = os.path.join(temp_dir, "output")
        zip_path = os.path.join(temp_dir, "result.zip")
        log_stream = io.StringIO()

        runtime_config = build_runtime_config(
            app.state.base_config,
            input_folder=app.state.input_folder,
            output_folder=output_dir,
            excel_folder=app.state.excel_folder,
            languages=available_languages,
            languages_to_run=resolved_languages,
        )

        try:
            with redirect_stdout(log_stream), redirect_stderr(log_stream):
                result = run_conversion(runtime_config)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": str(exc),
                    "log": log_stream.getvalue(),
                },
            ) from exc

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("log.txt", log_stream.getvalue())
            archive.writestr("summary.json", json.dumps(result["statistics"], indent=2))
            for file_path in sorted(path for path in Path(output_dir).iterdir() if path.is_file()):
                archive.write(file_path, arcname=file_path.name)

        filename_hint = "_".join(resolved_languages[:3]) if resolved_languages else "run"
        filename_hint = filename_hint[:120]
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"valpal-conversion-{filename_hint}.zip",
            background=BackgroundTask(cleanup_temp_dir, temp_dir),
        )

    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Run the ValPaL FastAPI server")
    parser.add_argument("--input-folder", required=True)
    parser.add_argument("--excel-folder", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main():
    import uvicorn

    args = parse_args()
    app = create_app(
        input_folder=args.input_folder,
        excel_folder=args.excel_folder,
        db_path=args.db_path,
        config_path=args.config_path,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
