# -*- coding: utf-8 -*-

# Section 1: Initial setup, imports and logging configuration

print("⚡ Starting 🚀Simple server ...")

# Essential libraries for core functionality
import yt_dlp            # YouTube-DL fork for video downloading with extended features
import subprocess        # For executing external commands (mkvmerge, etc.)
import re                # Regular expressions for pattern matching
import sys               # System-specific parameters and functions
from http.server import BaseHTTPRequestHandler, HTTPServer  # Basic HTTP server implementation
import urllib.parse      # Tools for URL parsing and manipulation
import time              # Time-related functions for timing and delays
import logging           # Logging infrastructure
import json              # JSON parsing and generation
import os                # Operating system interfaces
import unicodedata       # Unicode character database for normalisation
import difflib           # Sequence comparison tools
import shutil            # High-level file operations
import tempfile          # Temporary file creation
import socket            # Low-level networking interface
import datetime          # Date and time manipulation
import traceback         # Stack trace handling for error reporting
from pathlib import Path  # Object-oriented filesystem paths
from mutagen.id3 import ID3, USLT  # MP3 tag manipulation for embedding lyrics
import random            # For randomized delays
import platform          # For detecting OS to customize user agent

# Configure logging with timestamp format
logging.basicConfig(level=logging.INFO, format="%(message)s %(asctime)s")

class CustomLogFilter(logging.Filter):
    """
    Custom filter to suppress verbose and repetitive log messages.
    
    This filter checks log messages against a list of regular expression patterns
    and filters out any that match, keeping the console output clean and focused
    on important status updates.
    """
    def filter(self, record):
        # Comprehensive list of patterns to ignore in logs
        ignored_patterns = [
            r"Downloading video thumbnail",
            r"Video Thumbnail",
            r"Fetching SponsorBlock segments",
            r"No matching segments were found in the SponsorBlock database",
            r"Extracting cookies from",
            r"Extracted \d+ cookies",
            r"Writing video subtitles",
            r"Converting subtitles",
            r"Converting thumbnail",
            r"Deleting original file",
            r"Merging formats",
            r"Embedding subtitles",
            r"Adding metadata",
            r"\[SponsorBlock\]",
            r"Finished downloading playlist",
            r"\[youtube\]",
            r"\[info\]",
            r"\[SubtitlesConvertor\]",
            r"\[VideoRemuxer\]",
            r"\[EmbedSubtitle\]",
            r"\[EmbedThumbnail\]",
            r"cookies",
            r"^$",
            r"\[download\] \d+\.\d+KiB at",
            r"\[youtube\] Extracting URL",
            r"\[youtube\] .*: Downloading",
            r"SponsorBlock] Found \d+ segments",
            r"\[youtube:tab\] Incomplete data received",
        ]

        # Check if the log message matches any of the patterns to be ignored
        log_message = record.getMessage()
        return not any(re.search(pattern, log_message) for pattern in ignored_patterns)

# Setup logging with custom filter
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addFilter(CustomLogFilter())

# Error Handling Strategy:
# 1. Server-level errors (handle_connection_error function) - handles errors in the server's main loop
# 2. Handler-level errors (BatchRequestHandler.handle_error method) - handles errors during HTTP request processing
# This dual-layer approach ensures ConnectionAbortedError is gracefully handled regardless of where it occurs
def handle_connection_error(request, client_address):
    """
    Custom error handler for server-level connection errors.
    
    This function provides a clean error message when a connection is aborted at the server level,
    preventing verbose stack traces from appearing in the console output.
    
    Args:
        request: The client request object
        client_address: A tuple containing the client's address information
    """
    error_type, error_value, _ = sys.exc_info()
    if isinstance(error_value, ConnectionAbortedError):
        print("\n❌ Connection lost")
        print("─────────────────")
        print("😎 Ready")
    else:
        # Let the original handler process other types of errors
        traceback.print_exc()

# Define the path to the config file
SETTINGS_FILE = "Simple_settings.json"

# Section 2: Port management and settings

# Check if port is available
def is_port_available(port):
    """
    Check if a specific network port is available for use.
    
    Attempts to bind to the specified port to determine if it's free.
    
    Args:
        port (int): The port number to check
        
    Returns:
        bool: True if the port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
            return True
    except OSError:
        return False

# Find an available port
def find_available_port(start_port=16868, max_attempts=10):
    """
    Find an available port starting from a specified port number.
    
    Tries incrementing port numbers until finding an available one,
    falling back to a random high port if necessary.
    
    Args:
        start_port (int): The initial port to check (default: 16868)
        max_attempts (int): Maximum number of consecutive ports to try (default: 10)
        
    Returns:
        int: An available port number
    """
    port = start_port
    attempts = 0
    
    while attempts < max_attempts:
        if is_port_available(port):
            return port
        port += 1
        attempts += 1
    
    # If we've tried too many ports, fall back to a random high port
    return find_random_high_port()

def find_random_high_port():
    """
    Find a random available high-numbered port.
    
    Uses the system's port allocation mechanism to find a free port
    in the ephemeral port range.
    
    Returns:
        int: An available port number in the high range
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

# Load settings
def load_settings():
    """
    Load application settings from the settings file.
    
    Reads download folder path and port settings from a JSON file.
    Creates default settings if the file doesn't exist or is invalid.
    Processes relative paths and expands environment variables.
    
    Returns:
        dict: A dictionary containing the application settings
    """
    default_settings = {
        "folder": "",
        "port": 16868,
        "use_browser_cookies": False  # New setting for cookie usage control
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as file:
                settings = json.load(file)
                
                # Ensure we have all required keys with default values if missing
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                
                # Process folder path
                folder_path = settings["folder"].strip()
                folder_path = folder_path.replace("{HOME}", str(Path.home()))

                if not folder_path or not os.path.isabs(folder_path):
                    folder_path = Path.home() / "Downloads" / "Simple downloads"
                
                settings["folder"] = str(Path(folder_path).resolve())
                
                return settings
        except json.JSONDecodeError:
            print("⚠ Error reading settings file. Using defaults.")
    
    # If file doesn't exist or has issues, create with defaults
    default_settings["folder"] = str(Path.home() / "Downloads" / "Simple downloads")
    save_settings(default_settings)
    return default_settings

def save_settings(settings):
    """
    Save application settings to the settings file.
    
    Writes the current settings to a JSON file for persistence
    between application runs.
    
    Args:
        settings (dict): Dictionary containing the application settings
    """
    try:
        with open(SETTINGS_FILE, "w") as file:
            json.dump(settings, file, indent=4)
        print(f"✅ Saved settings: folder={settings['folder']}, port={settings['port']}, use_browser_cookies={settings.get('use_browser_cookies', False)}")
    except Exception as e:
        print(f"❌ ERROR: Could not save {SETTINGS_FILE}: {e}")

# Load settings
settings = load_settings()
DEFAULT_DOWNLOAD_FOLDER = Path(settings["folder"])
DEFAULT_PORT = settings["port"]
USE_BROWSER_COOKIES = settings.get("use_browser_cookies", False)

# Ensure the folder exists
DEFAULT_DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Get a realistic user agent based on the operating system
def get_system_user_agent():
    """
    Returns a realistic user agent string based on the user's operating system.
    
    This helps make requests appear more like normal browser traffic.
    
    Returns:
        str: A user agent string appropriate for the system
    """
    system = platform.system()
    if system == "Windows":
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    elif system == "Darwin":  # macOS
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    else:  # Linux and others
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# System user agent to be used in requests
SYSTEM_USER_AGENT = get_system_user_agent()

# Section 3: URL and file processing utilities

def clean_video_url(url):
    """
    Remove playlist parameters from YouTube video URLs.
    
    For YouTube videos that are part of a playlist, this extracts just
    the video ID and creates a clean URL without playlist parameters,
    ensuring only the specific video is downloaded.
    
    Args:
        url (str): The YouTube URL, potentially with playlist parameters
        
    Returns:
        str: A clean URL with only the video ID
    """
    if "youtube.com/watch" in url and "&list=" in url:
        # Extract the video ID
        video_id_match = re.search(r'v=([^&]+)', url)
        if video_id_match:
            video_id = video_id_match.group(1)
            # Return clean URL with just the video ID
            return f"https://www.youtube.com/watch?v={video_id}"
    return url

# Temporary directory management functions
def get_temp_processing_dir():
    """
    Create and return a persistent temporary directory for processing downloads.
    
    Creates a platform-specific temporary directory for intermediate files
    during download processing. On Windows, uses LocalAppData, and on other
    platforms, uses the home directory's cache folder.
    
    Returns:
        Path: Path object pointing to the temporary processing directory
    """
    if sys.platform == "win32":
        base_dir = Path(os.getenv('LOCALAPPDATA')) / "SimpleDownloader" / "temp"
    else:
        base_dir = Path.home() / ".cache" / "SimpleDownloader" / "temp"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def cleanup_temp_dir(temp_dir):
    """
    Remove all files in the temporary directory.
    
    Cleans up the temporary processing directory by removing all files
    and recreating the empty directory.
    
    Args:
        temp_dir (Path): The temporary directory to clean
    """
    try:
        shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        logging.debug("✨ Cleaned up temporary files")
    except Exception as e:
        logging.error(f"❌ Error cleaning temporary directory: {e}")

# Folder management functions
def load_folder():
    """
    Return the current download folder path.
    
    Returns:
        Path: Path object pointing to the current download folder
    """
    return DEFAULT_DOWNLOAD_FOLDER

def save_folder(folder):
    """
    Save a new download folder path to settings.
    
    Updates the application settings with a new download folder path
    and saves the settings to the configuration file.
    
    Args:
        folder (str): The new download folder path
    """
    try:
        settings["folder"] = str(folder)
        save_settings(settings)
        print(f"✅ Saved default folder: {folder}")
    except Exception as e:
        print(f"❌ ERROR: Could not save folder setting: {e}")

    global DEFAULT_DOWNLOAD_FOLDER
    DEFAULT_DOWNLOAD_FOLDER = Path(folder)

# Toggle browser cookie usage
def set_use_browser_cookies(use_cookies):
    """
    Set whether to use browser cookies for downloads.
    
    Updates the settings to toggle whether browser cookies are used
    for video downloading.
    
    Args:
        use_cookies (bool): Whether to use browser cookies
    """
    try:
        settings["use_browser_cookies"] = bool(use_cookies)
        save_settings(settings)
        print(f"✅ Browser cookie usage set to: {use_cookies}")
        
        global USE_BROWSER_COOKIES
        USE_BROWSER_COOKIES = bool(use_cookies)
    except Exception as e:
        print(f"❌ ERROR: Could not save cookie setting: {e}")

# Filename and subtitle handling functions
def normalise_filename(name):
    """
    Remove problematic characters and normalise special symbols in filenames.
    
    Applies Unicode normalisation to convert special characters to their
    canonical form and converts to lowercase for case-insensitive comparisons.
    
    Args:
        name (str): The filename to normalise
        
    Returns:
        str: Normalised filename
    """
    return unicodedata.normalize('NFKC', name).lower()

# Section 4: Subtitle and lyrics processing

def convert_srt_timestamp(srt_time):
    """
    Convert SRT timestamp (00:00:00,000) to LRC format [mm:ss.xx].
    
    Transforms subtitle timestamps from SRT format to LRC format for
    lyrics embedding in MP3 files.
    
    Args:
        srt_time (str): Timestamp in SRT format (HH:MM:SS,mmm)
        
    Returns:
        str: Timestamp in LRC format [mm:ss.xx] or None if parsing fails
    """
    pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    match = re.match(pattern, srt_time)
    if not match:
        return None
    
    h, m, s, ms = map(int, match.groups())
    total_minutes = h * 60 + m
    return f"[{total_minutes:02d}:{s:02d}.{ms//10:02d}]"

def fix_TED_lyrics_before_embedding_in_mp3(srt_file):
    """
    Fix formatting of first subtitle block in TED audio transcripts.
    
    TED subtitles often have a malformed first subtitle block that needs
    special handling. This function also adds a 3585ms offset to all
    timestamps to adjust for audio delay.
    
    Args:
        srt_file (str): Path to the SRT subtitle file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Pattern focusing on the dual timestamp structure
        pattern = r'1\n00:00:00,000 --> 00:00:00,001\n\s*\n(\d{2}:\d{2}:\d{2})\.(\d{3}) -- (\d{2}:\d{2}:\d{2})\.(\d{3})\n(.*?)\n(?=\d+\n\d{2}:\d{2}:\d{2},)'
        
        # Replace with correctly formatted subtitle block
        replacement = r'1\n\1,\2 --> \3,\4\n\5\n'
        
        # Fix the malformed first subtitle
        content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)
        
        # Add 3585ms to all timestamps
        def add_offset(match):
            start, end = match.groups()
            start_parts = start.split(',')
            end_parts = end.split(',')
            
            # Add offset to start time
            h, m, s = map(int, start_parts[0].split(':'))
            ms = int(start_parts[1]) + 3585
            s += ms // 1000
            ms = ms % 1000
            m += s // 60
            s = s % 60
            h += m // 60
            m = m % 60
            new_start = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            
            # Add offset to end time
            h, m, s = map(int, end_parts[0].split(':'))
            ms = int(end_parts[1]) + 3585
            s += ms // 1000
            ms = ms % 1000
            m += s // 60
            s = s % 60
            h += m // 60
            m = m % 60
            new_end = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            
            return f"{new_start} --> {new_end}"
        
        # Apply the offset to all timestamps
        content = re.sub(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', add_offset, content)
        
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return True
    except Exception as e:
        logging.error(f"❌ Error fixing TED subtitle format: {e}")
        return False

def fix_TED_lyrics_and_embed_in_mkv(mkv_file, srt_file):
    """
    Fix formatting of first subtitle block and embed in MKV file.
    
    Similar to fix_TED_lyrics_before_embedding_in_mp3, but embeds the
    fixed subtitles into an MKV video file using mkvmerge external tool.
    
    Args:
        mkv_file (str): Path to the MKV video file
        srt_file (str): Path to the SRT subtitle file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First modify the SRT file
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Pattern focusing on the dual timestamp structure
        pattern = r'1\n00:00:00,000 --> 00:00:00,001\n\s*\n(\d{2}:\d{2}:\d{2})\.(\d{3}) -- (\d{2}:\d{2}:\d{2})\.(\d{3})\n(.*?)\n(?=\d+\n\d{2}:\d{2}:\d{2},)'
        
        # Replace with correctly formatted subtitle block
        replacement = r'1\n\1,\2 --> \3,\4\n\5\n'
        
        # Fix the malformed first subtitle
        content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)
        
        # Add 3585ms to all timestamps
        def add_offset(match):
            start, end = match.groups()
            start_parts = start.split(',')
            end_parts = end.split(',')
            
            # Add offset to start time
            h, m, s = map(int, start_parts[0].split(':'))
            ms = int(start_parts[1]) + 3585
            s += ms // 1000
            ms = ms % 1000
            m += s // 60
            s = s % 60
            h += m // 60
            m = m % 60
            new_start = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            
            # Add offset to end time
            h, m, s = map(int, end_parts[0].split(':'))
            ms = int(end_parts[1]) + 3585
            s += ms // 1000
            ms = ms % 1000
            m += s // 60
            s = s % 60
            h += m // 60
            m = m % 60
            new_end = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            
            return f"{new_start} --> {new_end}"
        
        # Apply the offset to all timestamps
        content = re.sub(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', add_offset, content)
        
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Use mkvmerge to embed the modified subtitles
        temp_output = mkv_file + ".temp.mkv"
        merge_command = [
            "mkvmerge",
            "-o", temp_output,
            mkv_file,
            "--language", "0:eng",
            "--track-name", "0:English",
            srt_file
        ]
        
        result = subprocess.run(
            merge_command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if result.returncode != 0:
            logging.error(f"❌ Error embedding TED subtitles: {result.stderr}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
            
        # Replace original file with the new one
        os.replace(temp_output, mkv_file)
        return True
        
    except Exception as e:
        logging.error(f"❌ Error processing TED subtitles: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False

def embed_lyrics_in_mp3(mp3_file, srt_file):
    """
    Convert SRT to LRC format and embed in MP3 using ID3v2.3.
    
    Reads subtitles from an SRT file, converts them to LRC format,
    and embeds them as synchronised lyrics in an MP3 file.
    
    Args:
        mp3_file (str): Path to the MP3 file
        srt_file (str): Path to the SRT subtitle file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(mp3_file) or not mp3_file.lower().endswith('.mp3'):
            logging.error("❌ Invalid MP3 file for lyrics embedding")
            return False

        # Read and convert SRT content
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            content = re.sub(r'\\h+', ' ', content)
            blocks = re.split(r'\n\n+', content.strip())
            lrc_lines = []
            last_end_time = None
            
            for block in blocks:
                lines = block.split('\n')
                if len(lines) < 3:
                    continue
                
                timestamp_line = lines[1]
                text_lines = lines[2:]
                
                start_time, end_time = timestamp_line.split(' --> ')
                lrc_timestamp = convert_srt_timestamp(start_time)
                last_end_time = end_time
                
                if lrc_timestamp:
                    text = ' '.join(text_lines)
                    lrc_lines.append(f"{lrc_timestamp} {text}")

            # Add final empty timestamp
            if last_end_time:
                final_timestamp = convert_srt_timestamp(last_end_time)
                if final_timestamp:
                    lrc_lines.append(f"{final_timestamp}")

        if not lrc_lines:
            return False

        # Embed lyrics in MP3
        try:
            audio = ID3(mp3_file)
        except:
            audio = ID3()
        
        audio.version = (2, 3, 0)
        audio.delall("f")
        audio.add(USLT(encoding=3, lang='eng', text='\n'.join(lrc_lines)))
        audio.save(mp3_file, v2_version=3)
        logging.debug("✅ Embedded synchronised lyrics in MP3")
        return True

    except Exception as e:
        logging.error(f"❌ Error embedding lyrics: {e}")
        return False

# Section 5: File matching and platform detection

def find_closest_filename(expected_name, directory, desired_extension=None):
    """
    Find a file in the directory that closely matches the expected name.
    
    Handles case differences, special characters, and fuzzy matching
    to find an existing file that matches the expected filename.
    Optionally filters by file extension.
    
    Args:
        expected_name (str): The expected filename to match
        directory (str): Directory to search in
        desired_extension (str, optional): File extension to filter by
        
    Returns:
        str: Path to the matching file, or None if no match found
    """
    expected_normalised = normalise_filename(expected_name)
    all_files = os.listdir(directory)
    normalised_files = {normalise_filename(f): f for f in all_files}

    if desired_extension:
        desired_extension = desired_extension.lower()
        video_extensions = {'.mkv', '.mp4', '.webm'}
        
        for real_name in normalised_files.values():
            base_name = os.path.splitext(real_name)[0]
            ext = os.path.splitext(real_name)[1].lower()
            if (normalise_filename(base_name) == os.path.splitext(expected_normalised)[0] and 
                ext == desired_extension):
                return os.path.join(directory, real_name)
                
        for real_name in normalised_files.values():
            base_name = os.path.splitext(real_name)[0]
            ext = os.path.splitext(real_name)[1].lower()
            if normalise_filename(base_name) == os.path.splitext(expected_normalised)[0]:
                if (desired_extension == '.mp3' and ext in video_extensions) or \
                   (desired_extension in video_extensions and ext == '.mp3'):
                    return None
        
        return None

    if expected_normalised in normalised_files:
        return os.path.join(directory, normalised_files[expected_normalised])

    closest_match = difflib.get_close_matches(expected_normalised, normalised_files.keys(), n=1, cutoff=0.8)
    if closest_match:
        return os.path.join(directory, normalised_files[closest_match[0]])
    return None

# Platform detection and chapter handling
def is_supported_video_platform(url):
    """
    Check if the URL is from a supported video platform that might have chapters.
    
    Detects if the URL belongs to YouTube, TED, Vimeo, or Dailymotion
    using regular expression pattern matching.
    
    Args:
        url (str): URL to check
        
    Returns:
        tuple: (is_supported, platform_name)
            - is_supported (bool): True if the platform is supported
            - platform_name (str): Name of the detected platform
    """
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+',
        r'(?:https?://)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+'
    ]
    
    ted_patterns = [
        r'(?:https?://)?(?:www\.)?ted\.com/talks/[\w-]+',
        r'(?:https?://)?(?:www\.)?ted\.com/talks/lang/\w+/[\w-]+'
    ]
    
    vimeo_patterns = [
        r'(?:https?://)?(?:www\.)?vimeo\.com/\d+',
        r'(?:https?://)?player\.vimeo\.com/video/\d+'
    ]
    
    dailymotion_patterns = [
        r'(?:https?://)?(?:www\.)?dailymotion\.com/video/[\w]+',
        r'(?:https?://)?dai\.ly/[\w]+'
    ]
    
    combined_youtube = '|'.join(youtube_patterns)
    if re.match(combined_youtube, url):
        return True, "youtube"
    
    combined_ted = '|'.join(ted_patterns)
    if re.match(combined_ted, url):
        return True, "ted"
    
    combined_vimeo = '|'.join(vimeo_patterns)
    if re.match(combined_vimeo, url):
        return True, "vimeo"
    
    combined_dailymotion = '|'.join(dailymotion_patterns)
    if re.match(combined_dailymotion, url):
        return True, "dailymotion"
    
    return False, "unknown"

# Section 6: Chapter extraction functions

def extract_chapter_titles(url, chapters_xml):
    """
    Extracts chapters based on the video platform.
    
    Delegates to platform-specific extraction functions based on
    the detected video platform.
    
    Args:
        url (str): URL of the video
        chapters_xml (str): Path to save the extracted chapters XML
        
    Returns:
        bool: True if chapters were extracted successfully, False otherwise
    """
    is_supported, platform = is_supported_video_platform(url)
    
    if not is_supported:
        logging.debug(f"⚠️ No chapter extraction available for this URL type")
        return False
    
    if platform == "youtube":
        return extract_youtube_chapters(url, chapters_xml)
    elif platform == "ted":
        return extract_ted_chapters(url, chapters_xml)
    elif platform in ["vimeo", "dailymotion"]:
        logging.debug(f"⚠️ Chapter extraction for {platform} not yet implemented")
        return False
    else:
        logging.debug(f"⚠️ Unrecognised platform for chapter extraction")
        return False

def extract_youtube_chapters(url, chapters_xml):
    """
    Extracts both YouTube chapters and SponsorBlock chapters using yt-dlp.
    
    Gets chapter information from both the video's own chapter markers
    and the SponsorBlock community database, combining them into
    a single chapters XML file.
    
    Args:
        url (str): YouTube URL
        chapters_xml (str): Path to save the extracted chapters XML
        
    Returns:
        bool: True if chapters were extracted successfully, False otherwise
    """
    try:
        # Build the command with user agent and optional cookies
        cmd = ["yt-dlp", "--dump-json", "--sponsorblock-mark", "--user-agent", SYSTEM_USER_AGENT, url]
        
        # Only add cookies for YouTube if enabled
        if USE_BROWSER_COOKIES:
            cmd.insert(1, "--cookies-from-browser")
            cmd.insert(2, "firefox")
        
        result = subprocess.run(
            cmd,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        regular_chapters = []
        if result.stdout.strip():
            try:
                video_data = json.loads(result.stdout)
                if "chapters" in video_data:
                    regular_chapters = video_data["chapters"]
                    if regular_chapters:
                        logging.debug("✅ Chapters found")
                    else:
                        logging.debug("❌ No chapters available")
            except Exception as e:
                logging.debug("❌ No chapters available")
        else:
            logging.debug("❌ No chapters available")

        logging.debug("🔍 Getting SponsorBlock segments ...")
        sponsor_chapters = []
        if result.stdout.strip():
            try:
                video_data = json.loads(result.stdout)
                if "sponsorblock_chapters" in video_data and video_data["sponsorblock_chapters"]:
                    for segment in video_data["sponsorblock_chapters"]:
                        sponsor_chapters.append({
                            "start_time": segment["start_time"],
                            "end_time": segment["end_time"],
                            "title": f"[SponsorBlock] {segment['category']}"
                        })
                    logging.debug("✅ SponsorBlock segments found")
                else:
                    logging.debug("⚠️ No SponsorBlock segments available")
            except Exception as e:
                logging.debug("⚠️ No SponsorBlock segments available")
        else:
            logging.debug("⚠️ No SponsorBlock segments available")

        all_chapters = []
        
        for chapter in regular_chapters:
            all_chapters.append({
                "start_time": chapter["start_time"],
                "end_time": chapter["end_time"],
                "title": chapter["title"]
            })

        all_chapters.extend(sponsor_chapters)
        all_chapters.sort(key=lambda x: x["start_time"])

        if all_chapters:
            with open(chapters_xml, "w", encoding="utf-8") as f:
                for i, chapter in enumerate(all_chapters, 1):
                    start_ms = int(chapter["start_time"] * 1000)
                    hours = start_ms // 3600000
                    minutes = (start_ms % 3600000) // 60000
                    seconds = (start_ms % 60000) // 1000
                    milliseconds = start_ms % 1000
                    
                    timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                    f.write(f"CHAPTER{i:02d}={timestamp}\n")
                    f.write(f"CHAPTER{i:02d}NAME={chapter['title']}\n")

            logging.debug(f"✅ Created chapters.xml with {len(all_chapters)} chapters")
            return True
        else:
            return False

    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to extract chapter information: {e}")
        return False

def extract_ted_chapters(url, chapters_xml):
    """
    Extracts chapters from TED talks using yt-dlp's json output.
    
    Parses the video description to extract timestamp-based chapters
    that are common in TED talks.
    
    Args:
        url (str): TED talk URL
        chapters_xml (str): Path to save the extracted chapters XML
        
    Returns:
        bool: True if chapters were extracted successfully, False otherwise
    """
    try:
        # Build the command with user agent and optional cookies
        cmd = ["yt-dlp", "--dump-json", "--user-agent", SYSTEM_USER_AGENT, url]
        
        # Only add cookies for TED if enabled
        if USE_BROWSER_COOKIES:
            cmd.insert(1, "--cookies-from-browser")
            cmd.insert(2, "firefox")
            
        result = subprocess.run(
            cmd,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        if not result.stdout.strip():
            logging.debug("❌ No TED data available")
            return False
            
        try:
            video_data = json.loads(result.stdout)
            description = video_data.get("description", "")
            
            timestamp_pattern = r'(?:^|\n)(?P<time>\d{1,2}:(?:\d{1,2})(?::\d{1,2})?) (?P<title>.*?)(?=\n\d{1,2}:|$)'
            timestamps = re.finditer(timestamp_pattern, description)
            
            chapters = []
            for match in timestamps:
                time_str = match.group('time')
                title = match.group('title').strip()
                
                parts = time_str.split(':')
                if len(parts) == 2:  # MM:SS format
                    minutes, seconds = map(int, parts)
                    start_time = minutes * 60 + seconds
                elif len(parts) == 3:  # HH:MM:SS format
                    hours, minutes, seconds = map(int, parts)
                    start_time = hours * 3600 + minutes * 60 + seconds
                else:
                    continue
                
                chapters.append({
                    "start_time": start_time,
                    "end_time": start_time + 1,
                    "title": title
                })
            
            chapters.sort(key=lambda x: x["start_time"])
            
            for i in range(len(chapters) - 1):
                chapters[i]["end_time"] = chapters[i + 1]["start_time"]
            
            if "duration" in video_data and chapters:
                chapters[-1]["end_time"] = video_data["duration"]
            
            if chapters:
                with open(chapters_xml, "w", encoding="utf-8") as f:
                    for i, chapter in enumerate(chapters, 1):
                        start_ms = int(chapter["start_time"] * 1000)
                        hours = start_ms // 3600000
                        minutes = (start_ms % 3600000) // 60000
                        seconds = (start_ms % 60000) // 1000
                        milliseconds = start_ms % 1000
                        
                        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                        f.write(f"CHAPTER{i:02d}={timestamp}\n")
                        f.write(f"CHAPTER{i:02d}NAME={chapter['title']}\n")
                
                logging.debug(f"✅ Created chapters.xml with {len(chapters)} TED chapters")
                return True
            else:
                logging.debug("⚠️ No chapters found in TED talk description")
                return False
                
        except json.JSONDecodeError:
            logging.debug("❌ Failed to parse TED video data")
            return False
            
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to extract TED chapter information: {e}")
        return False

def apply_chapters_to_mkv(mkv_file, chapters_xml):
    """
    Applies the updated chapters.xml to the MKV file.
    
    Uses mkvpropedit external tool to embed chapter information into
    the MKV file.
    
    Args:
        mkv_file (str): Path to the MKV file
        chapters_xml (str): Path to the chapters XML file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["mkvpropedit", mkv_file, "--chapters", chapters_xml],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        if result.stderr:
            logging.error(f"❌ mkvpropedit error: {result.stderr.strip()}")
            return False

        return True

    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to apply chapters: {e}")
        return False

# Section 7: Video processing main functions

def process_single_video(handler, url, audio_only, temp_processing_dir, item_num=1, total_items=1, limit_to_1080p=False, use_mp4=False):
    """
    Process a single video download completely - from download to final file move.
    
    This is the core function that handles the entire process of downloading
    a video from a supported platform, processing it according to parameters
    and saving it to the destination folder. Includes special handling for
    various platforms and formats.
    
    Args:
        handler: The HTTP request handler instance
        url (str): URL of the video to download
        audio_only (bool): Whether to extract audio only (MP3)
        temp_processing_dir (Path): Temporary directory for processing
        item_num (int): Current item number in a playlist
        total_items (int): Total number of items in a playlist
        limit_to_1080p (bool): Whether to limit video resolution to 1080p
        
    Returns:
        tuple: (processed_file, file_size_bytes)
            - processed_file (str): Name of the processed file
            - file_size_bytes (int): Size of the processed file in bytes
    """
    
    # Facebook detection - check if it's a Facebook URL
    is_facebook = "facebook.com" in url.lower() or "fb.com" in url.lower() or "fb.watch" in url.lower()
    
    # Check if we should use cookies for this URL
    is_auth_site = "youtube.com" in url.lower() or "youtu.be" in url.lower() or is_facebook
    
    # Apply randomized delay to mimic human behavior and reduce detection
    if item_num > 1:
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)
    
    # Get expected filename for this video
    url = clean_video_url(url)
    
    # Build the filename command with user agent and optional cookies
    filename_command = [
        "yt-dlp",
        "--print", "filename",
        "--user-agent", SYSTEM_USER_AGENT,
        "-o", "%(title)s.%(ext)s",  # Specify output template without ID
        "-P", str(DEFAULT_DOWNLOAD_FOLDER),
        url
    ]
    
    # Only add cookies if enabled and for sites that require authentication
    if USE_BROWSER_COOKIES and is_auth_site:
        filename_command.insert(1, "--cookies-from-browser")
        filename_command.insert(2, "firefox")
    
    try:
        filename_result = subprocess.run(
            filename_command,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False
        )
        
        if not filename_result.stdout.strip():
            logging.error("❌ No video found")
            print(f"───────────────────────────────────────────")
            print(f"😎 Ready")
            return None, 0
        
        output_filename = filename_result.stdout.strip()
        base_name = os.path.splitext(os.path.basename(output_filename))[0]
        
        # Handle generic Facebook filenames with timestamp-based unique name
        if is_facebook and (base_name == "Facebook" or base_name == "Video"):
            # Create a timestamp-based unique ID for generic Facebook videos
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            unique_id = f"{base_name}-{timestamp}"
            print(f"🗃️ Downloading (Facebook video title not retrieved so adding timestamp to keep the name unique):\n　 {unique_id}")
            base_name = unique_id
            output_filename = Path(output_filename).with_stem(unique_id)
        else:
            print(f"🗃️ Downloading (filename may be temporarily sanitised):\n➡️ {base_name}")
        
        # Prepare final filename
        final_extension = ".mp3" if audio_only else ".mp4" if use_mp4 else ".mkv"
        final_filepath = Path(output_filename).with_suffix(final_extension)
        final_destination = DEFAULT_DOWNLOAD_FOLDER / final_filepath.name
        
        # Check for existing file - but skip this for renamed Facebook videos (they should be unique now)
        if not (is_facebook and (base_name.startswith("Facebook-") or base_name.startswith("Video-"))):
            existing_file = find_closest_filename(final_filepath.name, DEFAULT_DOWNLOAD_FOLDER, final_extension)
            if existing_file:
                logging.info(f"✅ Skipping download, file already exists: {Path(existing_file).name}")
                return Path(existing_file).name, Path(existing_file).stat().st_size
        
        # For Facebook videos with generic names, modify the yt-dlp output template
        yt_dlp_output_template = "%(title)s.%(ext)s"
        if is_facebook and (base_name.startswith("Facebook-") or base_name.startswith("Video-")):
            yt_dlp_output_template = f"{base_name}.%(ext)s"
        
        # Check if it's a TED video
        is_ted_video = is_supported_video_platform(url)[1] == "ted"
        
        # Build base command parameters with user agent
        yt_dlp_command = [
            "yt-dlp",
            "--user-agent", SYSTEM_USER_AGENT,
            "--no-mtime",
            "--no-playlist",
            "-o", yt_dlp_output_template,
            "-P", str(temp_processing_dir),
            "--convert-thumbnails", "png",
            "--embed-thumbnail",
            "--add-metadata",
            "--sub-lang", "en.*",
            "--convert-subs", "srt",
            "--newline",
            url
        ]
        
        # Only add cookies if enabled and for sites that require authentication
        if USE_BROWSER_COOKIES and is_auth_site:
            yt_dlp_command.insert(1, "--cookies-from-browser")
            yt_dlp_command.insert(2, "firefox")
        
        # Add format-specific parameters based on conditions
        if not audio_only:
            if not is_ted_video:
                # Regular video download with embedded subs
                if limit_to_1080p:
                    # Format string when limited to 1080p
                    yt_dlp_command += [
                        "-f", "(bestvideo[hdr=1][height<=1080])/(bestvideo[bit_depth=10][height<=1080])/(bestvideo[height<=1080])+(bestaudio)/b[height<=1080]",
                        "--merge-output-format", "mp4" if use_mp4 else "mkv",
                        "--remux-video", "mp4" if use_mp4 else "mkv",
                        "--audio-format", "aac"
                    ]
                    
                    # Only add these features for MKV format
                    if not use_mp4:
                        yt_dlp_command += [
                            "--embed-subs",
                            "--sub-format", "srt/best",
                            "--sponsorblock-mark", "all,-music_offtopic,-poi_highlight"
                        ]
                else:
                    # HDR prioritised format string when no 1080p limit set
                    yt_dlp_command += [
                        "-f", "(bestvideo[hdr=1])/(bestvideo[bit_depth=10])+(bestaudio)/bv*+ba/b",
                        "--merge-output-format", "mp4" if use_mp4 else "mkv",
                        "--remux-video", "mp4" if use_mp4 else "mkv",
                        "--audio-format", "aac"
                    ]
                    
                    # Only add these features for MKV format
                    if not use_mp4:
                        yt_dlp_command += [
                            "--embed-subs",
                            "--sub-format", "srt/best",
                            "--sponsorblock-mark", "all,-music_offtopic,-poi_highlight"
                        ]
            else:
                # TED video - download subs separately
                yt_dlp_command += [
                    "-f", "bv*+ba/b",
                    "--merge-output-format", "mp4" if use_mp4 else "mkv",
                    "--remux-video", "mp4" if use_mp4 else "mkv",
                    "--audio-format", "aac",
                    "--write-sub",
                    "--sub-format", "srt/best",
                    "--sponsorblock-mark", "all,-music_offtopic,-poi_highlight"
                ]
        else:
            # Audio-only downloads always get separate subtitle handling
            yt_dlp_command += [
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--write-sub"
            ]
        
        # Clean URL to remove playlist parameters
        yt_dlp_command[-1] = clean_video_url(yt_dlp_command[-1])
        
        # Start download with progress tracking
        current_video_url = url
        thumbnail_embedded = False
        file_info = f" (File {item_num}/{total_items})" if total_items > 1 else ""
        
        # Clear flags for download type detection
        is_downloading_audio = False
        is_downloading_video = False
        is_downloading_metadata = False
        
        # State tracking
        download_count = 0
        download_sequence = []
        has_downloaded_mp4 = False
        
        process = subprocess.Popen(
            yt_dlp_command,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
                
            if output:
                # Detect what's currently downloading
                if "[download]" in output and "Destination:" in output:
                    # Reset flags
                    is_downloading_audio = False
                    is_downloading_video = False
                    is_downloading_metadata = False
                    download_count += 1
                    
                    # For TED videos, use a simple index-based approach
                    # First = metadata, Second = video, Third = audio
                    if is_ted_video and not audio_only:
                        if ".vtt" in output.lower() or ".srt" in output.lower() or ".json" in output.lower() or ".jpg" in output.lower() or ".png" in output.lower():
                            is_downloading_metadata = True
                            download_sequence.append("metadata")
                        elif download_count == 2:
                            is_downloading_video = True
                            has_downloaded_mp4 = True
                            download_sequence.append("video")
                        elif download_count == 3:
                            is_downloading_audio = True
                            download_sequence.append("audio")
                        else:
                            # Default to metadata for any additional files
                            is_downloading_metadata = True
                            download_sequence.append("metadata")
                    else:
                        # For all other video sites
                        if any(ext in output.lower() for ext in [".srt", ".vtt", ".jpg", ".png", ".json", ".ytdl"]):
                            is_downloading_metadata = True
                        elif audio_only:
                            is_downloading_audio = True
                        elif any(ext in output.lower() for ext in [".m4a", ".mp3", ".aac", ".opus", ".weba", ".ogg", ".wav", ".flac", ".ac3", ".mka"]):
                            is_downloading_audio = True
                        elif ".f" in output and any(format_id in output for format_id in ["140", "249", "250", "251", "139", "171", "258"]):
                            is_downloading_audio = True
                        elif any(indicator in output.lower() for indicator in ["audio only", "audio_only", "audio stream", "audio track", "audio-only"]):
                            is_downloading_audio = True
                        elif any(pattern in output.lower() for pattern in ["audio-high", "-audio-", "dash_audio", "audio_track", "audio-track", "audio_mp4", "audio-mp4", "mp4-audio", "audio_segment", "audio=", "audio_only=true"]):
                            is_downloading_audio = True
                        else:
                            is_downloading_video = True
                    
                # Handle progress updates
                progress_match = re.search(r'\[download\]\s+(\d+\.\d+)% of', output)
                if progress_match:
                    progress = progress_match.group(1)
                    sys.stdout.write('\r' + ' ' * 70 + '\r')  # Clear line
                    
                    if is_downloading_metadata:
                        msg = f"📄 Downloading metadata: {progress}%"
                    elif is_downloading_video:
                        msg = f"📽️ Downloading video: {progress}%"
                    elif is_downloading_audio:
                        msg = f"🎧 Downloading audio: {progress}%"
                    else:
                        msg = f"📥 Downloading: {progress}%"
                        
                    if file_info:
                        msg += file_info
                    sys.stdout.write(msg)
                    sys.stdout.flush()
        
        # Replace final progress line with "Done" message
        if download_count > 0:
            sys.stdout.write('\r' + ' ' * 70 + '\r')  # Clear line
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S") + f",{now.microsecond // 1000:03d}"
            file_info = f" (File {item_num}/{total_items})" if total_items > 1 else ""
            done_msg = f"💯 Done{file_info} 💥 {timestamp}"
            sys.stdout.write(done_msg + '\n')
            sys.stdout.flush()
        
        # Process downloaded file
        processed_file = None
        file_size_bytes = 0
        
        # Wait for file
        retries = 0
        max_retries = 10
        while retries < max_retries:
            download_files = list(temp_processing_dir.glob(f"*.{'mp3' if audio_only else 'mp4' if use_mp4 else 'mkv'}"))
            if download_files:
                break
            time.sleep(0.5)
            retries += 1
            
        if not download_files:
            logging.error(f"❌ No downloaded file found for: {final_filepath.name}")
            return None, 0
        
        file_path = download_files[0]
        
        # Handle audio processing
        if audio_only:
            # Process TED audio or regular audio
            srt_files = list(temp_processing_dir.glob("*.srt"))
            matching_srt = None
            for srt in srt_files:
                if any(part in file_path.stem for part in srt.stem.split('.')):
                    matching_srt = srt
                    break
            
            if matching_srt:
                if is_ted_video:
                    if fix_TED_lyrics_before_embedding_in_mp3(str(matching_srt)):
                        if embed_lyrics_in_mp3(str(file_path), str(matching_srt)):
                            logging.info("🎧 Embedded TED transcript in MP3")
                        else:
                            logging.warning("⚠️ Failed to embed TED transcript")
                else:
                    if embed_lyrics_in_mp3(str(file_path), str(matching_srt)):
                        logging.info("🎧 Embedded synchronised lyrics/transcript in MP3")
                    else:
                        logging.warning("⚠️ No lyrics/transcript available")
                try:
                    os.remove(matching_srt)
                    logging.debug(f"🧹 Deleted temporary subtitle file: {matching_srt.name}")
                except Exception as e:
                    logging.error(f"❌ Error deleting subtitle file: {e}")

        # Handle video processing
        if not audio_only:
            if is_ted_video:
                # Process TED video subtitles
                srt_files = list(temp_processing_dir.glob("*.srt"))
                matching_srt = None
                for srt in srt_files:
                    if any(part in file_path.stem for part in srt.stem.split('.')):
                        matching_srt = srt
                        break
                
                if matching_srt:
                    if fix_TED_lyrics_and_embed_in_mkv(str(file_path), str(matching_srt)):
                        logging.info("🗨️ Embedded TED subtitles in MKV")
                    else:
                        logging.warning("⚠️ Failed to embed TED subtitles")
                    try:
                        os.remove(matching_srt)
                    except Exception as e:
                        logging.error(f"❌ Error deleting subtitle file: {e}")
            else:
                # Handle chapters for supported platforms (skip for MP4)
                if not use_mp4:
                    is_supported, platform = is_supported_video_platform(current_video_url)
                    if is_supported:
                        logging.debug(f"📥 Getting chapters from {platform} ...")
                        chapters_xml = Path(temp_processing_dir) / f"{file_path.stem}_chapters.xml"
                        
                        if extract_chapter_titles(current_video_url, str(chapters_xml)):
                            logging.debug("📌 Applying chapters to MKV ...")
                            apply_chapters_to_mkv(str(file_path), str(chapters_xml))
                            if os.path.exists(chapters_xml):
                                logging.debug(f"🧹 Cleaning up chapters file: {chapters_xml}")
                                os.remove(chapters_xml)

        # Move and finalise file
        final_destination = DEFAULT_DOWNLOAD_FOLDER / file_path.name
        shutil.move(str(file_path), str(final_destination))

        if final_destination.exists():
            file_size_bytes = final_destination.stat().st_size
            processed_file = final_destination.name
            
            # Only show individual file line for playlists
            if total_items > 1:
                file_size_mb = file_size_bytes / (1024 * 1024)
                formatted_size = f"{file_size_mb:.2f} MB" if file_size_mb >= 1 else f"{file_size_bytes / 1024:.2f} KB"
                emoji = "💿" if final_destination.suffix == '.mp3' else "📺"
                print(f"{emoji} {final_destination.name} ({formatted_size})")
            
            # Always print the separator
            print("─────────────────")
            
        # Cleanup
        leftover_files = list(temp_processing_dir.glob("*.*"))
        for leftover in leftover_files:
            try:
                os.remove(leftover)
            except Exception:
                pass
        
        return processed_file, file_size_bytes
        
    except subprocess.CalledProcessError as e:
        if "getaddrinfo failed" in str(e) or "network is unreachable" in str(e) or "socket error" in str(e):
            logging.error("❌ Network connection error - Please check your internet connection")
        else:
            logging.error(f"❌ Error processing URL: {url}. Details: {e}")
        return None, 0
    except Exception as e:
        logging.error(f"❌ Unexpected error processing {url}: {str(e)}")
        return None, 0

# Section 8: HTTP server implementation

class BatchRequestHandler(BaseHTTPRequestHandler):
    """
    Custom HTTP request handler for the download server.
    
    Handles HTTP requests for video downloads, folder settings
    and server information. Implements custom error handling
    for connection aborted errors.
    """
    def log_message(self, format, *args):
        """
        Override to suppress default server log messages.
        
        Args:
            format: Format string
            *args: Format arguments
        """
        pass

    def _set_headers(self, status_code=200, content_type="application/json"):
        """
        Set common HTTP response headers.
        
        Args:
            status_code (int): HTTP status code (default: 200)
            content_type (str): Content-Type header value (default: "application/json")
        """
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self._set_headers(200)

    def handle_error(self, request, client_address):
        """
        Override to suppress ConnectionAbortedError tracebacks during request processing.
        
        This catches connection errors that occur while sending responses to clients,
        which is different from the server-level handle_connection_error function.
        
        Args:
            request: The client request object
            client_address: A tuple containing the client's address information
        """
        error_type, error_value, _ = sys.exc_info()
        if isinstance(error_value, ConnectionAbortedError):
            print("\n❌ Connection lost")
            print("─────────────────")
            print("😎 Ready")
        else:
            super().handle_error(request, client_address)

    def do_GET(self):
        """
        Handle GET requests.
        
        Processes favicon requests, folder information requests,
        server information requests and download requests.
        """
        if self.path == "/favicon.ico":
            self._set_headers(204)
            return

        if self.path == "/folder":
            self._set_headers(200, "application/json")
            folder_response = {
                "folder": str(DEFAULT_DOWNLOAD_FOLDER).replace("\\", "/") if os.name != "nt" else str(DEFAULT_DOWNLOAD_FOLDER)
            }
            try:
                self.wfile.write(json.dumps(folder_response).encode())
            except ConnectionAbortedError:
                logging.debug("Connection aborted before response was fully sent.")
            return

        elif self.path == "/server-info":
            self._set_headers(200, "application/json")
            server_path = str(Path(__file__).parent.resolve())
            if not server_path:
                server_path = str(Path.home() / "Downloads" / "Simple downloads")

            server_info = {
                "server_path": server_path,
                "port": settings["port"],
                "use_browser_cookies": settings.get("use_browser_cookies", False)
            }
            try:
                self.wfile.write(json.dumps(server_info).encode())
            except ConnectionAbortedError:
                logging.debug("Connection aborted before response was fully sent.")
                return
            return

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "url" in params:
            url = params["url"][0]
            audio_only = params.get("audioOnly", [False])[0] == "true"
            limit_to_1080p = params.get("limitTo1080p", [False])[0] == "true"
            use_mp4 = params.get("useMP4", [False])[0] == "true"

            if not url:
                self._set_headers(400)
                self.wfile.write(b"Invalid URL provided")
                logging.error("Invalid URL received.")
                return

            logging.info("🚀 Download started 🪐")
            print(f"🌍 URL: {url}")
            print(f"🎧 Audio only?: {audio_only}\n📽️ Limit to max 1080p?: {limit_to_1080p}\n📼 Use MP4 format?: {use_mp4}\n🔎 Getting filename/playlist info ...")
            
            # Add user agent information
            print(f"🌐 Using UA: {SYSTEM_USER_AGENT.split('/')[0]}")
            print(f"🍪 Using browser cookies: {'✅ Yes' if USE_BROWSER_COOKIES else '❌ No'}")

            temp_processing_dir = get_temp_processing_dir()
            cleanup_temp_dir(temp_processing_dir)
            start_time = time.time()

            is_playlist_page = url.startswith("https://www.youtube.com/playlist?")
            
            try:
                processed_files = []
                total_size_bytes = 0
                
                if is_playlist_page:
                    # Build command with user agent
                    playlist_command = [
                        "yt-dlp",
                        "--user-agent", SYSTEM_USER_AGENT,
                        "--flat-playlist",
                        "--print", "%(id)s",
                        url
                    ]
                    
                    # Only add cookies for YouTube if enabled
                    if USE_BROWSER_COOKIES:
                        playlist_command.insert(1, "--cookies-from-browser")
                        playlist_command.insert(2, "firefox")
                    
                    playlist_result = subprocess.run(
                        playlist_command,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    video_ids = [id for id in playlist_result.stdout.strip().split('\n') if id]
                    num_files = len(video_ids)
                    
                    # Get playlist name once (with stderr capture to suppress warnings)
                    # Build command with user agent
                    playlist_name_cmd = [
                        "yt-dlp",
                        "--user-agent", SYSTEM_USER_AGENT,
                        "--flat-playlist",
                        "--print", "%(playlist_title)s",
                        url
                    ]
                    
                    # Only add cookies for YouTube if enabled
                    if USE_BROWSER_COOKIES:
                        playlist_name_cmd.insert(1, "--cookies-from-browser")
                        playlist_name_cmd.insert(2, "firefox")
                        
                    playlist_name_result = subprocess.run(
                        playlist_name_cmd,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE  # Capture stderr to prevent warnings
                    )
                    # Process playlist name from first valid line
                    playlist_name = "Unnamed Playlist"
                    if playlist_name_result.stdout.strip():
                        # Take first non-empty line
                        playlist_name = playlist_name_result.stdout.strip().split('\n')[0].strip()

                    print(f"📦 Playlist name: {playlist_name} ({num_files} videos)")
                    print("🗃️ Files to be downloaded (filenames may be temporarily sanitised):")
                    
                    # Get all filenames upfront
                    for idx, video_id in enumerate(video_ids, 1):
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        # Build command with user agent
                        filename_command = [
                            "yt-dlp",
                            "--user-agent", SYSTEM_USER_AGENT,
                            "--print", "filename",
                            "-o", "%(title)s.%(ext)s",
                            video_url
                        ]
                        
                        # Only add cookies for YouTube if enabled
                        if USE_BROWSER_COOKIES:
                            filename_command.insert(1, "--cookies-from-browser")
                            filename_command.insert(2, "firefox")
                            
                        filename_result = subprocess.run(
                            filename_command,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False
                        )
                        if filename_result.stdout.strip():
                            # Remove extension and print filename
                            base_filename = os.path.splitext(filename_result.stdout.strip())[0]
                            print(f"{idx}. {base_filename}")
                    
                    print("─────────────────")
                    
                    # Continue with processing each video, but add delay between them
                    for idx, video_id in enumerate(video_ids, 1):
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        processed_file, file_size = process_single_video(
                            self, video_url, audio_only, temp_processing_dir, idx, num_files, limit_to_1080p
                        )
                        
                        if processed_file:
                            processed_files.append({
                                'name': processed_file,
                                'size': format_size(file_size),
                                'size_bytes': file_size
                            })
                            total_size_bytes += file_size
                            
                    if len(processed_files) > 0:
                        logging.info("✅ Downloads complete 💃🕺")
                else:
                    processed_file, file_size = process_single_video(
                        self, url, audio_only, temp_processing_dir, 1, 1, limit_to_1080p, use_mp4
                    )
                    
                    if processed_file:
                        processed_files.append({
                            'name': processed_file,
                            'size': format_size(file_size),
                            'size_bytes': file_size
                        })
                        total_size_bytes += file_size
                
                cleanup_temp_dir(temp_processing_dir)
                
                elapsed_time = time.time() - start_time
                formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
                
                if len(processed_files) > 0:
                    print("💥 Download summary")
                    
                    for file_info in processed_files:
                        emoji = "💿" if file_info['name'].endswith('.mp3') else "📺"
                        print(f"{emoji} {file_info['name']} ({file_info['size']})")
                    
                    total_formatted = format_size(total_size_bytes)
                    print(f"📊 Total size: {total_formatted}")
                    print(f"📂 Saved in folder: {DEFAULT_DOWNLOAD_FOLDER}")
                    print("\n😎 Ready\n")
                
                    self._set_headers(200)
                    response_message = f"Download completed in {formatted_time}\n"
                    self.wfile.write(response_message.encode())
                else:
                    self._set_headers(404)
                    self.wfile.write(b"No files were downloaded")
                    
            except subprocess.CalledProcessError as e:
                self._set_headers(500)
                if "getaddrinfo failed" in str(e) or "network is unreachable" in str(e) or "socket error" in str(e):
                    self.wfile.write(b"Network connection error")
                    logging.error("❌ Network connection error - Please check your internet connection")
                else:
                    self.wfile.write(b"An error occurred while processing the URL")
                    logging.error(f"Error processing URL: {url}. Details: {e}")
            except ConnectionAbortedError:
                logging.info("📡 Connection interrupted - possibly due to network issues")
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(b"An unexpected error occurred")
                logging.error(f"❌ Unexpected error: {str(e)}")

        else:
            self._set_headers(400)
            self.wfile.write(b"No URL provided in the request")
            logging.error("No URL provided in the request.")

    def do_POST(self):
        """
        Handle POST requests.
        
        Processes folder setting requests.
        """
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        if self.path == "/set-folder":
            try:
                data = json.loads(post_data)
                new_folder = data.get("folder", "").strip()

                # ✅ Validate: Ensure it's an absolute path
                if not new_folder or not os.path.isabs(new_folder):
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"message": "❌ Invalid folder path. Please enter a full absolute path."}).encode())
                    logging.error(f"Invalid folder path: {new_folder}")
                    return

                new_folder_path = Path(new_folder)

                # ✅ Instead of rejecting, create the folder if it doesn't exist
                new_folder_path.mkdir(parents=True, exist_ok=True)

                # ✅ Ensure the folder is writeable
                if not os.access(new_folder_path, os.W_OK):
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"message": "❌ Folder exists but is not writable. Check permissions or disk space."}).encode())
                    logging.error(f"Folder exists but is not writable: {new_folder}")
                    return

                # ✅ Save new folder permanently
                save_folder(new_folder)

                self._set_headers(200)
                self.wfile.write(json.dumps({"message": "✅ Download folder updated."}).encode())
                logging.info(f"Download folder updated to: {DEFAULT_DOWNLOAD_FOLDER}")

            except Exception as e:
                logging.error(f"Error updating folder: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"message": "❌ Server error while updating folder."}).encode())
        
        elif self.path == "/set-cookie-usage":
            try:
                data = json.loads(post_data)
                use_cookies = data.get("useBrowserCookies", False)
                
                # Update the cookie usage setting
                set_use_browser_cookies(use_cookies)
                
                self._set_headers(200)
                self.wfile.write(json.dumps({"message": f"✅ Browser cookie usage set to: {'enabled' if use_cookies else 'disabled'}"}).encode())
                
            except Exception as e:
                logging.error(f"Error updating cookie settings: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"message": "❌ Server error while updating cookie settings."}).encode())

def format_size(size_bytes):
    """
    Format bytes as human-readable size.
    
    Converts raw byte count to a human-readable format in MB or KB.
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string with units
    """
    size_mb = size_bytes / (1024 * 1024)
    return f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size_bytes / 1024:.2f} KB"

# Server initialisation
port = find_available_port(DEFAULT_PORT)
if port != DEFAULT_PORT:
    print(f"⚠ Default port {DEFAULT_PORT} not available, using port {port}")
    settings["port"] = port
    save_settings(settings)
else:
    logging.debug(f"✅ Using port {port}")

server_address = ("", port)
httpd = HTTPServer(server_address, BatchRequestHandler)

# Log server status
print(f"✅ Server running on port {port}")
print(f"📂 Download folder is: {DEFAULT_DOWNLOAD_FOLDER}")
print(f"🍪 Browser cookie usage: {'✅ Enabled' if USE_BROWSER_COOKIES else '❌ Disabled (recommended)'}")
print(f"🌐 Using user agent: {SYSTEM_USER_AGENT.split(' ')[0]}")
print("\n😎 Ready\n")

# Assign custom error handler to the server to catch server-level connection errors
httpd.handle_error = handle_connection_error

# Start the server
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\n🚀 Downloads cancelled\n")
    print("✨ You need to restart the server to keep downloading")
    print('✨ To do that, type "python simple.py" (without the quotes) and press Enter')
    print("✨ (If you've done that before in this session, press the up arrow to save you typing)\n\n")
    sys.exit(0)
