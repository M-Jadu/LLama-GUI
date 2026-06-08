"""Benchmark dataset helper routes."""

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request as UrlRequest

from backend.http import sanitize_error


WIKITEXT2_URL = "https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip"
WIKITEXT2_DIR = "wikitext-2-raw-v1"
WIKITEXT2_TEST_FILE = "wiki.test.raw"


def _find_zip_member(archive):
    expected_suffix = f"/{WIKITEXT2_TEST_FILE}"
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        if member.is_dir():
            continue
        if name == WIKITEXT2_TEST_FILE or name.endswith(expected_suffix):
            return member
    return None


def ensure_wikitext2(request, response, ctx):
    dataset_dir = ctx.paths.models / WIKITEXT2_DIR
    target = dataset_dir / WIKITEXT2_TEST_FILE

    if target.exists():
        response.json({"ready": True, "downloaded": False, "path": str(target)})
        return

    dataset_dir.mkdir(parents=True, exist_ok=True)

    try:
        req = UrlRequest(WIKITEXT2_URL, headers={"User-Agent": "Llama-GUI"})
        with ctx.services.urlopen_with_ssl(req, timeout=60) as upstream:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = Path(tmp.name)
                shutil.copyfileobj(upstream, tmp)

        try:
            with zipfile.ZipFile(tmp_path) as archive:
                member = _find_zip_member(archive)
                if member is None:
                    response.error("WikiText-2 test file was not found in the downloaded archive.", 500)
                    return
                with archive.open(member) as src, open(target, "wb") as dest:
                    shutil.copyfileobj(src, dest)
        finally:
            tmp_path.unlink(missing_ok=True)

        response.json({"ready": True, "downloaded": True, "path": str(target)})
    except Exception as exc:
        print(f"WikiText-2 download failed: {exc}", file=sys.stderr, flush=True)
        response.error(sanitize_error(exc, 500), 500)
