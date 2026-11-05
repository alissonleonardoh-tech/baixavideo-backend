import os
import re
import tempfile
import pathlib
import secrets
import shutil
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.responses import FileResponse
import yt_dlp

app = FastAPI(title="BaixaVideo Backend", docs_url=None, redoc_url=None)
MAX_BYTES = 100 * 1024 * 1024

@app.get("/health")
def health():
    return {"ok": True, "extractor": yt_dlp.version.__version__, "ffmpeg": shutil.which("ffmpeg") is not None}

def require_key(value):
    expected = os.getenv("DOWNLOAD_API_KEY")
    if not expected or not value or not secrets.compare_digest(value, expected):
        raise HTTPException(401, "Não autorizado")

def validate_url(url):
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower()
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            raise ValueError()
        if not (host == "xhamster.com" or host.endswith(".xhamster.com")):
            raise ValueError()
        if not re.match(r"^/(?:videos|embed)/", u.path):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(400, "Apenas links HTTPS de vídeos públicos do xHamster são aceitos")

@app.get("/probe")
def probe(url: str, x_api_key: str | None = Header(None)):
    require_key(x_api_key)
    validate_url(url)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "socket_timeout": 15}) as ydl:
            info = ydl.extract_info(url, download=False)
        return {"available": True, "title": info.get("title"), "duration": info.get("duration"), "extractor": info.get("extractor_key")}
    except Exception:
        raise HTTPException(422, "Não foi possível acessar o vídeo. O site pode exigir verificação de idade, login ou bloquear extração.")

def cleanup(path):
    shutil.rmtree(path, ignore_errors=True)

@app.get("/download")
def download(url: str, background_tasks: BackgroundTasks, x_api_key: str | None = Header(None)):
    require_key(x_api_key)
    validate_url(url)
    folder = tempfile.mkdtemp(prefix="bv-")
    try:
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20,
                "retries": 1, "fragment_retries": 1, "max_filesize": MAX_BYTES,
                "format": "best[ext=mp4][height<=720]/best[height<=720]/best",
                "outtmpl": os.path.join(folder, "video.%(ext)s"),
                "merge_output_format": "mp4", "restrictfilenames": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        matches = [p for p in pathlib.Path(folder).iterdir() if p.is_file() and not p.name.endswith(".part")]
        if not matches:
            raise ValueError("Arquivo não gerado")
        path = matches[0]
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Vídeo acima de 100 MB")
        background_tasks.add_task(cleanup, folder)
        return FileResponse(str(path), media_type="video/mp4" if path.suffix == ".mp4" else "application/octet-stream", filename=path.name)
    except Exception:
        cleanup(folder)
        raise HTTPException(422, "Não foi possível baixar este vídeo. Pode haver restrições de acesso ou tamanho.")
