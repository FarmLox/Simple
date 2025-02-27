# -*- coding: utf-8 -*-

print("⚡ Starting 🚀Simple server ...")

import yt_dlp
import subprocess
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import time
import logging
import json
import os
import unicodedata
import difflib
import shutil
import tempfile
from pathlib import Path
from mutagen.id3 import ID3, USLT

# Configure logging first
logging.basicConfig(level=logging.INFO, format="%(message)s %(asctime)s")

class CustomLogFilter(logging.Filter):
    def filter(self, record):
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

        log_message = record.getMessage()
        return not any(re.search(pattern, log_message) for pattern in ignored_patterns)

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addFilter(CustomLogFilter())

# Log server status first
print(f"✅ Server running on port 8080")

# Temporary directory management functions
def get_temp_processing_dir():
    """Create and return a persistent temporary directory for processing downloads."""
    if sys.platform == "win32":
        base_dir = Path(os.getenv('LOCALAPPDATA')) / "SimpleDownloader" / "temp"
    else:
        base_dir = Path.home() / ".cache" / "SimpleDownloader" / "temp"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def cleanup_temp_dir(temp_dir):
    """Remove all files in the temporary directory."""
    try:
        shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        logging.debug("✨ Cleaned up temporary files")
    except Exception as e:
        logging.error(f"❌ Error cleaning temporary directory: {e}")

# Define the path to the config file
FOLDER_FILE = "Simple_download_folder.json"

# Folder management functions
def load_folder():
    if os.path.exists(FOLDER_FILE):
        try:
            with open(FOLDER_FILE, "r") as file:
                data = json.load(file)
                folder_path = data.get("folder", "").strip()
                folder_path = folder_path.replace("{HOME}", str(Path.home()))

                if not folder_path or not os.path.isabs(folder_path):
                    folder_path = Path.home() / "Downloads" / "Simple downloads"

                return Path(folder_path).resolve()

        except json.JSONDecodeError:
            print("⚠ Error reading folder file. Using last known folder.")

    last_known_folder = Path(__file__).parent.resolve()
    print(f"⚠ Using last known server folder: {last_known_folder}")
    return last_known_folder

def save_folder(folder):
    try:
        with open(FOLDER_FILE, "w") as file:
            json.dump({"folder": str(folder)}, file, indent=4)
        print(f"✅ Saved default folder: {folder}")
    except Exception as e:
        print(f"❌ ERROR: Could not save {FOLDER_FILE}: {e}")

    global DEFAULT_DOWNLOAD_FOLDER
    DEFAULT_DOWNLOAD_FOLDER = folder

# Load and initialise folder
DEFAULT_DOWNLOAD_FOLDER = load_folder()
print(f"📂 Download folder is: {DEFAULT_DOWNLOAD_FOLDER}\n\n😎 Ready\n")

# Ensure the folder exists
DEFAULT_DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Filename and subtitle handling functions
def normalise_filename(name):
    """Remove problematic characters and normalise special symbols."""
    return unicodedata.normalize('NFKC', name).lower()

def convert_srt_timestamp(srt_time):
    """Convert SRT timestamp (00:00:00,000) to LRC format [mm:ss.xx]"""
    pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    match = re.match(pattern, srt_time)
    if not match:
        return None
    
    h, m, s, ms = map(int, match.groups())
    total_minutes = h * 60 + m
    return f"[{total_minutes:02d}:{s:02d}.{ms//10:02d}]"

def fix_TED_lyrics_before_embedding_in_mp3(srt_file):
    """Fix formatting of first subtitle block in TED audio transcripts."""
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
    """Fix formatting of first subtitle block and embed in MKV file."""
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
    """Convert SRT to LRC format and embed in MP3 using ID3v2.3"""
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

def find_closest_filename(expected_name, directory, desired_extension=None):
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
    """Check if the URL is from a supported video platform that might have chapters."""
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

def extract_chapter_titles(url, chapters_xml):
    """Extracts chapters based on the video platform."""
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
    """Extracts both YouTube chapters and SponsorBlock chapters using yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--sponsorblock-mark", url],
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
    """Extracts chapters from TED talks using yt-dlp's json output."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", url],
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
    """Applies the updated chapters.xml to the MKV file."""
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

def process_single_video(handler, url, audio_only, temp_processing_dir, item_num=1, total_items=1):
    """Process a single video download completely - from download to final file move."""
    
    # Facebook detection - check if it's a Facebook URL
    is_facebook = "facebook.com" in url.lower() or "fb.com" in url.lower() or "fb.watch" in url.lower()
    
    # Get expected filename for this video
    filename_command = [
        "yt-dlp",
        "--print", "filename",
        "--cookies-from-browser", "firefox",
        "-o", "%(title)s.%(ext)s",  # Specify output template without ID
        "-P", str(DEFAULT_DOWNLOAD_FOLDER),
        url
    ]
    
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
            print(f"🗃️ Downloading (filename may be temporarily sanitised):\n　 {base_name}")
        
        # Prepare final filename
        final_extension = ".mp3" if audio_only else ".mkv"
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
        
        # Base command parameters
        yt_dlp_command = [
            "yt-dlp",
            "--no-mtime",
            "--cookies-from-browser", "firefox",
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
        
        # Add format-specific parameters based on conditions
        if not audio_only:
            if not is_ted_video:
                # Regular video download with embedded subs
                yt_dlp_command += [
                    "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                    "--merge-output-format", "mkv",
                    "--remux-video", "mkv",
                    "--audio-format", "aac",
                    "--embed-subs",
                    "--sub-format", "srt/best",
                    "--sponsorblock-mark", "all,-music_offtopic,-poi_highlight"
                ]
            else:
                # TED video - download subs separately
                yt_dlp_command += [
                    "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                    "--merge-output-format", "mkv",
                    "--remux-video", "mkv",
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
                        elif any(ext in output.lower() for ext in [".m4a", ".mp3", ".aac", ".opus", ".weba"]):
                            is_downloading_audio = True
                        elif ".f" in output and any(format_id in output for format_id in ["140", "249", "250", "251", "139", "171"]):
                            is_downloading_audio = True
                        elif "audio only" in output.lower():
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
                    elif is_downloading_audio:
                        msg = f"🎧 Downloading audio: {progress}%"
                    elif is_downloading_video:
                        msg = f"📺 Downloading video: {progress}%"
                    else:
                        msg = f"📥 Downloading: {progress}%"
                        
                    if file_info:
                        msg += file_info
                    sys.stdout.write(msg)
                    sys.stdout.flush()
        
        # Add a newline after progress displays
        if download_count > 0:
            sys.stdout.write("\n")
        
        # Process downloaded file
        processed_file = None
        file_size_bytes = 0
        
        # Wait for file
        retries = 0
        max_retries = 10
        while retries < max_retries:
            download_files = list(temp_processing_dir.glob(f"*.{'mp3' if audio_only else 'mkv'}"))
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
                # Handle chapters for supported platforms
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
            file_size_mb = file_size_bytes / (1024 * 1024)
            formatted_size = f"{file_size_mb:.2f} MB" if file_size_mb >= 1 else f"{file_size_bytes / 1024:.2f} KB"
            
            emoji = "💿" if final_destination.suffix == '.mp3' else "📺"
            logging.info(f"🚀 Done 💥")
            print(f"{emoji} {final_destination.name} ({formatted_size}\n─────────────────")
            processed_file = final_destination.name
            
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

class BatchRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _set_headers(self, status_code=200, content_type="application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
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

            server_info = {"server_path": server_path}
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

            if not url:
                self._set_headers(400)
                self.wfile.write(b"Invalid URL provided")
                logging.error("Invalid URL received.")
                return

            logging.info("🚀 Download started 🪐")
            print(f"🌍 URL: {url}")
            print(f"🎧 Audio only?: {audio_only}\n🔎 Getting filename/playlist info ...")

            temp_processing_dir = get_temp_processing_dir()
            cleanup_temp_dir(temp_processing_dir)
            start_time = time.time()

            is_playlist_page = url.startswith("https://www.youtube.com/playlist?")
            
            try:
                processed_files = []
                total_size_bytes = 0
                
                if is_playlist_page:
                    playlist_command = [
                        "yt-dlp",
                        "--flat-playlist",
                        "--print", "%(id)s",
                        "--cookies-from-browser", "firefox",
                        url
                    ]
                    
                    playlist_result = subprocess.run(
                        playlist_command,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    video_ids = [id for id in playlist_result.stdout.strip().split('\n') if id]
                    num_files = len(video_ids)
                    
                    # Get playlist name once (with stderr capture to suppress warnings)
                    playlist_name_cmd = [
                        "yt-dlp",
                        "--flat-playlist",
                        "--print", "%(playlist_title)s",
                        "--cookies-from-browser", "firefox",
                        url
                    ]
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
                        filename_command = [
"yt-dlp",
                            "--print", "filename",
                            "--cookies-from-browser", "firefox",
                            "-o", "%(title)s.%(ext)s",
                            video_url
                        ]
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
                    
                    # Continue with processing each video
                    for idx, video_id in enumerate(video_ids, 1):
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        processed_file, file_size = process_single_video(
                            self, video_url, audio_only, temp_processing_dir, idx, num_files
                        )
                        
                        if processed_file:
                            processed_files.append({
                                'name': processed_file,
                                'size': format_size(file_size),
                                'size_bytes': file_size
                            })
                            total_size_bytes += file_size
                            
                    if len(processed_files) > 0:
                        logging.info("✅ Downloads complete")
                else:
                    processed_file, file_size = process_single_video(
                        self, url, audio_only, temp_processing_dir
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
                    print("🚀 Download summary 💥💥")
                    
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

                # ✅ Reload from the JSON file after updating
                global DEFAULT_DOWNLOAD_FOLDER
                DEFAULT_DOWNLOAD_FOLDER = load_folder()

                # ✅ Ensure folder file is saved at least once
                if not os.path.exists(FOLDER_FILE):
                    print(f"📂 Creating {FOLDER_FILE} with default folder: {DEFAULT_DOWNLOAD_FOLDER}")
                    save_folder(DEFAULT_DOWNLOAD_FOLDER)
                else:
                    print(f"📂 {FOLDER_FILE} already exists. Skipping creation.")

                self._set_headers(200)
                self.wfile.write(json.dumps({"message": "✅ Download folder updated."}).encode())
                logging.info(f"Download folder updated to: {DEFAULT_DOWNLOAD_FOLDER}")

            except Exception as e:
                logging.error(f"Error updating folder: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"message": "❌ Server error while updating folder."}).encode())

def format_size(size_bytes):
    """Format bytes as human-readable size."""
    size_mb = size_bytes / (1024 * 1024)
    return f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size_bytes / 1024:.2f} KB"

# Server initialisation
server_address = ("", 8080)
httpd = HTTPServer(server_address, BatchRequestHandler)

# Start the server
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\n🚀 Downloads cancelled\n")
    print("✨ You need to restart the server to keep downloading")
    print('✨ To do that, type "python start.py" (without the quotes) and press Enter')
    print("✨ (If you've done that before in this session, press the up arrow to save you typing)\n\n")
    sys.exit(0)
