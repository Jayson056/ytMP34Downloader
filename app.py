from flask import Flask, render_template, request, Response, redirect, url_for, send_file
import yt_dlp
import re
import os
import platform
from pathlib import Path
from threading import Lock

app = Flask(__name__)


# Define paths dynamically based on OS
def get_download_path():
    """Determines the best download path based on the OS."""
    system_name = platform.system().lower()

    if "windows" in system_name:
        return Path.home() / "Downloads/YT_Downloads"
    elif "darwin" in system_name:  # macOS
        return Path.home() / "Downloads/YT_Downloads"
    elif "linux" in system_name:
        return Path.home() / "Downloads/YT_Downloads"
    elif "android" in system_name:
        return Path("/storage/emulated/0/Download/YT_Downloads"
                    )  # Default Android path
    else:
        return Path.cwd() / "downloads"  # Fallback for unknown OS


# Set up download and upload directories
BASE_DOWNLOAD_DIR = get_download_path()
UPLOAD_FOLDER = Path.cwd() / "uploads"
COOKIES_FILE = UPLOAD_FOLDER / "cookies.txt"

# Ensure directories exist
BASE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Lock to prevent concurrent downloads
download_lock = Lock()

COOKIE_STORAGE_PATH = "cookies.txt"  # Path to store cookies for yt-dlp


@app.route('/update-cookies', methods=['POST'])
def update_cookies():
    cookies_content = request.form.get('cookies')

    if cookies_content:
        try:
            # Save the cookies to the cookies.txt file
            with open(COOKIES_FILE, 'w') as cookies_file:
                cookies_file.write(cookies_content)
            print(f"Cookies updated: {COOKIES_FILE}")
            return redirect(url_for('convert_to_mp3'))
        except Exception as e:
            print(f"Error saving cookies: {e}")
            return "Error saving cookies.", 500
    return "No cookies provided.", 400


@app.route('/receive-cookies', methods=['POST'])
def receive_cookies():
    """Receives cookies from the client and saves them."""
    data = request.get_json()
    cookies = data.get('cookies')

    if not cookies:
        return jsonify({"error": "No cookies received"}), 400

    try:
        # Save cookies to a file (simulate a cookies.txt format)
        with open(COOKIE_STORAGE_PATH, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies.split(
                    "; "):  # Convert string to key-value pairs
                name, value = cookie.split("=")
                f.write(f"youtube.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")

        print("Cookies received and saved.")
        return jsonify({"message": "Cookies saved successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def sanitize_filename(title):
    """Ensure the filename is safe and does not contain invalid characters."""
    return re.sub(r'[<>:"/\\|?*]', '', title)


def get_video_info(link, req_format):
    """Extract YouTube video info and get direct download link."""
    if req_format not in ['mp3', 'mp4']:
        return None

    try:
        print("Fetching video information...")

        if not re.match(
                r'^(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+',
                link):
            print("Unsupported link:", link)
            return None

        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'cookiefile': str(COOKIES_FILE) if COOKIES_FILE.exists() else None
        }

        ydl_opts[
            "format"] = "bestaudio/best" if req_format == "mp3" else "bestvideo+bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info

    except Exception as e:
        print(f"Error fetching video info: {e}")
        return None


@app.route('/')
def convert_to_mp3():
    return render_template('ConvertToMp3.html')


@app.route('/convert-to-mp4')
def convert_to_mp4():
    return render_template('ConvertToMp4.html')


@app.route('/upload')
def upload_cookies():
    return render_template('UploadCookies.html')


@app.route('/upload-cookies', methods=['POST'])
def upload_cookies_file():
    """Handles the upload of the cookies.txt file."""
    file = request.files.get('cookies')
    if file and file.filename.endswith('.txt'):
        file.save(COOKIES_FILE)
        print(f"Cookies file uploaded to: {COOKIES_FILE}")
        return redirect(url_for('convert_to_mp3'))
    return "Invalid file or no file uploaded. Please upload a valid cookies.txt file.", 400


@app.route('/download', methods=['POST'])
def download_mp3():
    """Downloads only the audio as MP3 and serves it directly to the client."""
    link = request.form.get('link')

    with download_lock:
        info = get_video_info(link, 'mp3')
        if not info:
            return render_template('UploadCookies.html')

        sanitized_title = sanitize_filename(info.get('title', 'Unknown'))

        # Prepare the output file name without actually saving to server
        # Use the streaming functionality with yt-dlp and FFmpeg to send the file directly to the client
        ydl_opts = {
            'format':
            'bestaudio/best',
            'outtmpl':
            f"/tmp/{sanitized_title}.%(ext)s",  # Temporary location (only for processing)
            'quiet':
            True,
            'cookiefile':
            COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }

        try:
            print(f"Starting download for: {sanitized_title}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            # Now that the file is downloaded, we know it exists in the /tmp folder
            mp3_path = f"/tmp/{sanitized_title}.mp3"
            if not os.path.exists(mp3_path):
                return "MP3 download failed (file missing).", 500

            # Serve the file as an attachment directly to the client
            print(f"Serving MP3 file: {mp3_path}")
            return send_file(mp3_path,
                             as_attachment=True,
                             download_name=f"{sanitized_title}.mp3",
                             mimetype="audio/mp3")

        except Exception as e:
            print(f"MP3 Download error: {e}")
            return "MP3 download failed.", 500


@app.route('/download-mp4', methods=['POST'])
def download_mp4():
    """Downloads video + audio as MP4 and merges them."""
    link = request.form.get('link')

    with download_lock:
        info = get_video_info(link, 'mp4')
        if not info:
            return "Error retrieving video info.", 400

        sanitized_title = sanitize_filename(info.get('title', 'Unknown'))
        output_file = BASE_DOWNLOAD_DIR / f"{sanitized_title}.mp4"

        ydl_opts = {
            'format':
            'bestvideo+bestaudio/best',
            'outtmpl':
            str(output_file),
            'merge_output_format':
            'mp4',
            'quiet':
            True,
            'cookiefile':
            str(COOKIES_FILE) if COOKIES_FILE.exists() else None,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }]
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            if not output_file.exists():
                print(f"MP4 File not found: {output_file}")
                return "MP4 download failed (file missing).", 500

        except Exception as e:
            print(f"MP4 Download error: {e}")
            return "MP4 download failed.", 500

        return send_file(output_file, as_attachment=True)


@app.route('/serve-file/<filename>')
def serve_file(filename):
    """Serves the downloaded MP3 or MP4 file."""
    file_path = BASE_DOWNLOAD_DIR / filename

    # Debug: Print if the file exists
    if not file_path.exists():
        print(f"File Not Found: {file_path}")
        return "File not found.", 404

    mimetype = "audio/mp3" if filename.endswith(".mp3") else "video/mp4"
    return send_file(file_path, mimetype=mimetype, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
