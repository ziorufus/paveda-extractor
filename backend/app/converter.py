"""Thin wrapper around scripts/converter_core.py that works with Excel files stored in the DB."""

import io
import json
import os
import sys
import tempfile
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.converter_core import run_conversion  # noqa: E402

# run_conversion prints its log to stdout, which is process-wide: one conversion at a time
_conversion_lock = threading.Lock()


@dataclass
class ConversionResult:
    success: bool
    log: str
    statistics: dict | None
    error_count: int
    warning_count: int


def _count_lines(log, prefix):
    return sum(1 for line in log.splitlines() if line.lstrip().startswith(prefix))


def convert(app_config, languages, output_dir):
    """Run the converter.

    languages: list of (project.to_language_dict(), excel_filename, excel_bytes), in run order.
    output_dir: where the CSV files are written.
    """
    with tempfile.TemporaryDirectory(prefix="valpal-excel-") as excel_dir:
        language_map = {}
        for language, excel_filename, excel_bytes in languages:
            Path(excel_dir, excel_filename).write_bytes(excel_bytes)
            language_map[excel_filename] = language

        config = deepcopy(app_config)
        config.update(
            {
                "excel_folder": excel_dir,
                # Meanings/microroles file stays in the configured Excel folder (an absolute path wins in os.path.join)
                "new_mm_file": os.path.join(app_config["excel_folder"], app_config["new_mm_file"]),
                "output_folder": str(output_dir),
                "languages": language_map,
                "languages_to_run": list(language_map),
                "sets": {},
            }
        )

        log_stream = io.StringIO()
        statistics = None
        success = True
        with _conversion_lock:
            try:
                with redirect_stdout(log_stream), redirect_stderr(log_stream):
                    result = run_conversion(config)
                statistics = json.loads(json.dumps(result["statistics"], default=str))
            except Exception:
                success = False
                log_stream.write("\n\n### Conversion failed\n\n")
                log_stream.write(traceback.format_exc())

    log = log_stream.getvalue()
    return ConversionResult(
        success=success,
        log=log,
        statistics=statistics,
        error_count=_count_lines(log, "ERR"),
        warning_count=_count_lines(log, "WARN"),
    )


def check_excel(app_config, project, excel_bytes):
    """Convert a single language into a throwaway folder, only to collect the log.

    Alternation classes are skipped: they come from the shared alt-classes folder, not from this
    language's Excel file, so their errors would be wrongly attributed to it.
    """
    config = {**app_config, "perform_alt_classes": False}
    with tempfile.TemporaryDirectory(prefix="valpal-check-") as output_dir:
        return convert(config, [(project.to_language_dict(), project.excel_filename, excel_bytes)], output_dir)
