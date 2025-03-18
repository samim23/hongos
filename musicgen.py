"""Music generation module for video background music."""

import os
import logging
import subprocess
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from moviepy.editor import AudioFileClip
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def extract_youtube_id(youtube_url):
    """
    Extract YouTube video ID from various URL formats.
    
    Args:
        youtube_url (str): YouTube URL or video ID
        
    Returns:
        str: YouTube video ID or None if not found
    """
    # If it's already just an ID (11 characters)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', youtube_url):
        return youtube_url
    
    # Try to parse as URL
    try:
        parsed_url = urlparse(youtube_url)
        
        # Standard youtube.com URL
        if parsed_url.netloc in ('youtube.com', 'www.youtube.com') and parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        
        # Shortened youtu.be URL
        if parsed_url.netloc == 'youtu.be':
            return parsed_url.path[1:]  # Remove leading slash
        
        # YouTube embed URL
        if parsed_url.netloc in ('youtube.com', 'www.youtube.com') and parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        
    except Exception as e:
        log.error(f"Error parsing YouTube URL: {str(e)}")
    
    return None

def download_audio_from_youtube(youtube_url, output_dir=None, output_filename="background_music.mp3"):
    """
    Download audio from a YouTube video using yt-dlp.
    
    Args:
        youtube_url (str): YouTube URL or video ID
        output_dir (str): Directory to save the audio file
        output_filename (str): Name of the output audio file
        
    Returns:
        str: Path to the downloaded audio file or None if failed
    """
    try:
        # Check if input is a video ID rather than a full URL
        if not youtube_url.startswith(('http://', 'https://')):
            youtube_url = f"https://www.youtube.com/watch?v={youtube_url}"
        
        log.info(f"Downloading audio from YouTube: {youtube_url}")
        log.info(f"Output directory: {output_dir}")
        log.info(f"Output filename: {output_filename}")
        
        # Create temporary directory if output_dir is not specified
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, output_filename)
        log.info(f"Full output path: {output_path}")
        
        # Use yt-dlp to download only the audio
        command = [
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", "mp3",  # Convert to mp3
            "--audio-quality", "0",  # Best quality
            "-o", output_path,  # Output file
            youtube_url  # URL
        ]
        
        log.info(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            log.error(f"Error downloading audio: {result.stderr}")
            return None
            
        # Check if the file was actually created
        if os.path.exists(output_path):
            log.info(f"Successfully downloaded audio to: {output_path}")
            return output_path
        else:
            # Check if yt-dlp created a file with a different extension
            base_path = os.path.splitext(output_path)[0]
            possible_files = [f for f in os.listdir(output_dir) if f.startswith(os.path.basename(base_path))]
            if possible_files:
                actual_path = os.path.join(output_dir, possible_files[0])
                log.info(f"Found audio file with different name: {actual_path}")
                return actual_path
            else:
                log.error(f"No audio file found in {output_dir} after download")
                return None
    except Exception as e:
        log.error(f"Exception in download_audio_from_youtube: {str(e)}")
        return None

def trim_audio_to_length(audio_path, target_duration, output_path=None):
    """
    Trim an audio file to a specific duration.
    
    Args:
        audio_path (str): Path to the audio file
        target_duration (float): Target duration in seconds
        output_path (str): Path to save the trimmed audio file
        
    Returns:
        str: Path to the trimmed audio file or None if failed
    """
    try:
        if not os.path.exists(audio_path):
            log.error(f"Audio file not found: {audio_path}")
            return None
        
        # If no output path specified, create one
        if output_path is None:
            output_dir = os.path.dirname(audio_path)
            filename = os.path.basename(audio_path)
            output_path = os.path.join(output_dir, f"trimmed_{filename}")
        
        log.info(f"Trimming audio to {target_duration} seconds")
        
        # Load audio file
        audio_clip = AudioFileClip(audio_path)
        
        # Trim to target duration
        trimmed_clip = audio_clip.subclip(0, min(target_duration, audio_clip.duration))
        
        # Write output file
        trimmed_clip.write_audiofile(output_path, codec='mp3')
        
        # Close clips to free resources
        audio_clip.close()
        trimmed_clip.close()
        
        log.info(f"Successfully trimmed audio to {output_path}")
        return output_path
    
    except Exception as e:
        log.error(f"Error trimming audio: {str(e)}")
        return None

def adjust_audio_volume(audio_path, volume=0.3, output_path=None):
    """
    Adjust the volume of an audio file.
    
    Args:
        audio_path (str): Path to the audio file
        volume (float): Volume multiplier (0.0 to 1.0)
        output_path (str): Path to save the adjusted audio file
        
    Returns:
        str: Path to the adjusted audio file or None if failed
    """
    try:
        if not os.path.exists(audio_path):
            log.error(f"Audio file not found: {audio_path}")
            return None
        
        # If no output path specified, create one
        if output_path is None:
            output_dir = os.path.dirname(audio_path)
            filename = os.path.basename(audio_path)
            output_path = os.path.join(output_dir, f"adjusted_{filename}")
        
        log.info(f"Adjusting audio volume to {volume}")
        
        # Load audio file
        audio_clip = AudioFileClip(audio_path)
        
        # Adjust volume
        adjusted_clip = audio_clip.volumex(volume)
        
        # Write output file
        adjusted_clip.write_audiofile(output_path, codec='mp3')
        
        # Close clips to free resources
        audio_clip.close()
        adjusted_clip.close()
        
        log.info(f"Successfully adjusted audio volume to {output_path}")
        return output_path
    
    except Exception as e:
        log.error(f"Error adjusting audio volume: {str(e)}")
        return None

def prepare_background_music(youtube_url, output_dir, target_duration=None, volume_factor=0.3):
    """
    Download, trim, and adjust volume of background music from YouTube.
    
    Args:
        youtube_url (str): YouTube URL or video ID
        output_dir (str): Directory to save the audio files
        target_duration (float, optional): Target duration in seconds
        volume_factor (float, optional): Volume adjustment factor
        
    Returns:
        str: Path to the prepared background music file or None if failed
    """
    # Extract YouTube ID
    youtube_id = extract_youtube_id(youtube_url)
    if not youtube_id:
        log.error(f"Could not extract YouTube ID from: {youtube_url}")
        return None
    
    # Download audio
    audio_path = download_audio_from_youtube(youtube_url)
    if not audio_path:
        return None
    
    # Trim audio if target duration is specified
    if target_duration is not None:
        trimmed_path = trim_audio_to_length(audio_path, target_duration)
        if not trimmed_path:
            return None
        audio_path = trimmed_path
    
    # Adjust volume
    adjusted_path = adjust_audio_volume(audio_path, volume_factor)
    if not adjusted_path:
        return None
    
    return adjusted_path

if __name__ == "__main__":
    # Test functionality
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python musicgen.py <youtube_url_or_id> [output_dir]")
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    result = prepare_background_music(youtube_url, output_dir)
    if result:
        print(f"Successfully prepared background music: {result}")
    else:
        print("Failed to prepare background music")
