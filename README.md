# SaveNest, an independent downloader-style website

SaveNest recreates the general structure of classic green-and-white video link downloaders, but uses its own name, layout and implementation. It is **not affiliated with SaveFrom.net or YouTube**.

## Quick preview (no installation)
Double-click `index.html`. You can paste a YouTube URL and see the video thumbnail. The preview is a **demo only** and cannot download a file without the server.

## Start the functional local version (Windows)
1. Install Python 3.10 or newer from https://www.python.org/downloads/ and check **Add Python to PATH**.
2. Double-click `run_windows.bat`. It installs `yt-dlp` (internet connection needed) and launches the local server.
3. Go to **http://127.0.0.1:8765** and paste a normal YouTube video or Shorts URL.
4. Pick an available format. Browser downloads the MP4 if the source allows it.

For macOS/Linux: run `bash run_mac_linux.sh` from a terminal, and open the same local URL.

### 1080p and other HD formats
YouTube often offers high-resolution video and audio separately. Install **FFmpeg** and add it to your PATH to see those combined MP4 options. Without FFmpeg, progressive MP4s (often 360p or 720p) are offered when available.

### Important limitations
- Downloads are not guaranteed. Platforms change access rules and may require authentication or block automated requests.
- Does not bypass DRM, private-video permissions or other protections.
- Only YouTube video and Shorts URLs supported. Other social platforms intentionally not included.
- Local development demo, **not hardened for a public internet deployment**. Do not expose this built-in HTTP server to the public web without adding proper authentication, rate limiting, reverse proxy, job scheduling, bandwidth controls, legal review and more stringent resource limits.
- Maximum 60 minute length and 350 MB file size (approximate; actual streaming download constraints can vary).
- Only download content you own or have permission to download. Follow platform terms and local laws.

## Files
- `index.html`: responsive frontend, no frontend dependencies
- `server.py`: small local Python API + static server
- `requirements.txt`: yt-dlp dependency
- `run_windows.bat` and `run_mac_linux.sh`: local launchers
