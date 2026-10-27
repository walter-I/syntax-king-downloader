import ipaddress
import os
import socket
import threading
import uuid

from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, send_file, abort
from flask import request, url_for
from yt_dlp import YoutubeDL


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"

DOWNLOAD_DIR.mkdir(exist_ok=True)

MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_DOWNLOADS = 2
MAX_DURATION = 15 * 60  # 15 minutes

download_semaphore = threading.BoundedSemaphore(MAX_DOWNLOADS)


PLATFORMS = {
    "youtube": {
        "youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    },

    "instagram": {
        "instagram.com",
        "instagr.am",
    },

    "facebook": {
        "facebook.com",
        "m.facebook.com",
        "web.facebook.com",
        "fb.watch",
    },

    "tiktok": {
        "tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
    },
}


def validate_url(raw_url):
    """Validate the URL and reject non-public destinations."""

    if not isinstance(raw_url, str) or len(raw_url) > 2048:
        raise ValueError("Invalid or excessively long URL.")

    parsed = urlparse(raw_url)

    if parsed.scheme != "https":
        raise ValueError("Only HTTPS links are accepted.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid URL.")

    host = parsed.hostname.lower().rstrip(".")

    allowed = {
        domain
        for domains in PLATFORMS.values()
        for domain in domains
    }

    if host not in allowed:
        raise ValueError("This website is not supported.")

    try:
        addresses = socket.getaddrinfo(
            host,
            443,
            type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValueError("Unable to resolve the media website.")

    if not addresses:
        raise ValueError("Unable to resolve the media website.")

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])

        if not ip.is_global:
            raise ValueError("Non-public network destinations are blocked.")

    platform = next(
        name for name, domains in PLATFORMS.items()
        if host in domains
    )

    return platform


def download_media(url, job_id):
    """Download supported media into a uniquely named MP4 file."""

    output_template = str(DOWNLOAD_DIR / f"{job_id}.%(ext)s")

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "max_filesize": MAX_DOWNLOAD_SIZE,
        "socket_timeout": 20,
        "retries": 1,
        "fragment_retries": 1,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": False,
        "cachedir": False,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

        duration = info.get("duration")

        if duration is not None and duration > MAX_DURATION:
            raise ValueError(
                "This demo accepts media up to 15 minutes long."
            )

        if info.get("is_live"):
            raise ValueError("Live streams are not supported.")

        size = info.get("filesize") or info.get("filesize_approx")

        if size and size > MAX_DOWNLOAD_SIZE:
            raise ValueError("Media exceeds the 100 MB limit.")

        ydl.download([url])

    matches = list(DOWNLOAD_DIR.glob(f"{job_id}.*"))

    matches = [
        path for path in matches
        if path.is_file()
        and path.suffix.lower() in {
            ".mp4", ".webm", ".mkv", ".mov"
        }
    ]

    if not matches:
        raise RuntimeError("The download file was not created.")

    output_file = matches[0]

    if output_file.stat().st_size > MAX_DOWNLOAD_SIZE:
        output_file.unlink(missing_ok=True)
        raise ValueError("Downloaded media exceeds the size limit.")

    return output_file


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    if not request.is_json:
        return jsonify(error="Send a JSON request."), 400

    data = request.get_json(silent=True) or {}
    url = data.get("url", "")

    try:
        platform = validate_url(url)
    except (ValueError, StopIteration) as error:
        return jsonify(error=str(error)), 400

    # Do not start unlimited simultaneous downloads.
    if not download_semaphore.acquire(blocking=False):
        return jsonify(
            error="The server is busy. Try again shortly."
        ), 429

    job_id = uuid.uuid4().hex

    try:
        output_file = download_media(url, job_id)

        return jsonify(
            message=f"Media processed successfully from {platform}.",
            platform=platform,
            download_url=url_for(
                "get_download",
                job_id=job_id
            ),
        )

    except ValueError as error:
        return jsonify(error=str(error)), 400

    except Exception:
        app.logger.exception("Media processing failed")

        # Avoid exposing internal exceptions to users.
        return jsonify(
            error=(
                "Download failed. The media may be private, "
                "unsupported, unavailable, or restricted."
            )
        ), 502

    finally:
        download_semaphore.release()


@app.route("/download/<job_id>")
def get_download(job_id):
    if not job_id.isalnum() or len(job_id) != 32:
        abort(404)

    matches = list(DOWNLOAD_DIR.glob(f"{job_id}.*"))

    matches = [
        path for path in matches
        if path.is_file()
        and path.suffix.lower() in {
            ".mp4", ".webm", ".mkv", ".mov"
        }
    ]

    if not matches:
        abort(404)

    path = matches[0]

    return send_file(
        path,
        as_attachment=True,
        download_name=f"syntax-king-{job_id}{path.suffix}",
        conditional=True,
    )


if __name__ == "__main__":
    # Local development only. Do not expose the Flask debugger publicly.
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
