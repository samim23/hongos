# pip install elevenlabs
# pip install python-dotenv

from dotenv import load_dotenv
import os
import logging
import json
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# API key - replace with your actual key
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "your-elevenlabs-api-key")

def initialize_voice_client(api_key=None):
    """Initialize the ElevenLabs client with API key."""
    try:
        api_key_to_use = api_key if api_key else ELEVENLABS_API_KEY
        if not api_key_to_use:
            log.error("No ElevenLabs API key provided")
            return False
        
        # Create client
        client = ElevenLabs(api_key=api_key_to_use)
        return client
    except Exception as e:
        log.error(f"Error initializing ElevenLabs client: {str(e)}")
        return False

def generate_voice_for_caption(caption, speaker, output_path, voice_id="pNInz6obpgDQGcFmaJgB", api_key=None):
    """
    Generate audio for a caption using ElevenLabs API.
    
    Args:
        caption (str): The text to convert to speech
        speaker (str): Description of the speaker (used for voice selection)
        output_path (str): Path to save the audio file
        voice_id (str): ElevenLabs voice ID to use
        api_key (str, optional): ElevenLabs API key
    
    Returns:
        str: Path to the generated audio file or None if failed
    """
    if not caption:
        log.warning("Empty caption provided, skipping voice generation")
        return None
    
    try:
        # Initialize client
        client = initialize_voice_client(api_key)
        if not client:
            return None
        
        # Configure voice settings based on speaker description
        stability = 0.5
        similarity_boost = 0.5
        
        # Adjust voice settings based on speaker description
        if speaker and isinstance(speaker, str):
            speaker_lower = speaker.lower()
            
            # Adjust for formal/authoritative speakers
            if any(word in speaker_lower for word in ["formal", "authoritative", "narrator"]):
                stability = 0.7
                similarity_boost = 0.3
            
            # Adjust for emotional speakers
            if any(word in speaker_lower for word in ["excited", "cheerful", "humorous"]):
                stability = 0.3
                similarity_boost = 0.7
        
        # Generate audio
        log.info(f"Generating audio for caption: {caption[:50]}...")
        
        # Generate audio using the ElevenLabs client
        response = client.text_to_speech.convert(
            voice_id=voice_id,
            optimize_streaming_latency="0",
            output_format="mp3_44100_128",
            text=caption,
            model_id="eleven_monolingual_v1",
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=0.0,
                use_speaker_boost=True,
            ),
        )
        
        # Save the audio file
        with open(output_path, 'wb') as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
        
        log.info(f"Audio saved to {output_path}")
        return output_path
    
    except Exception as e:
        log.error(f"Error generating voice: {str(e)}")
        return None

def generate_voices_for_scenes(scenes_data, output_dir, api_key=None):
    """
    Generate voice files for all scenes in the data.
    
    Args:
        scenes_data (list): List of scene dictionaries
        output_dir (str): Directory to save audio files
        api_key (str, optional): ElevenLabs API key
    
    Returns:
        list: Updated scenes data with audio paths
    """
    # Create audio directory
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Log the total number of scenes
    log.info(f"Generating audio for {len(scenes_data)} scenes")
    
    # First, ensure all scenes have correct frame numbers
    # This is critical - we need to explicitly set frame_number for each scene
    # starting from 0 and incrementing by 1
    for i, scene in enumerate(scenes_data):
        scene["frame_number"] = i
        log.info(f"Set frame_number={i} for scene {i+1}")
    
    # Delete any existing audio files to prevent numbering conflicts
    if os.path.exists(audio_dir):
        for file in os.listdir(audio_dir):
            if file.endswith(".mp3"):
                try:
                    os.remove(os.path.join(audio_dir, file))
                    log.info(f"Removed existing audio file: {file}")
                except Exception as e:
                    log.warning(f"Could not remove file {file}: {str(e)}")
    
    # Process each scene
    for i, scene in enumerate(scenes_data):
        log.info(f"Processing scene {i}: {scene.get('caption', 'No caption')[:30]}...")
        
        if "caption" in scene and scene["caption"]:
            # Always use the loop index as the frame number (0-based)
            frame_num = i
            audio_filename = f"frame_{frame_num:03d}_audio.mp3"
            audio_path = os.path.join(audio_dir, audio_filename)
            
            # Log the file being created
            log.info(f"Generating audio for frame {frame_num}: {audio_filename}")
            
            # Generate audio
            result_path = generate_voice_for_caption(
                caption=scene["caption"],
                speaker=scene.get("speaker", "Narrator"),
                output_path=audio_path,
                api_key=api_key
            )
            
            # Update scene data with audio path
            if result_path:
                scene["audio_path"] = result_path
                log.info(f"Successfully generated audio for frame {frame_num}")
            else:
                log.warning(f"Failed to generate audio for frame {frame_num}")
        else:
            log.warning(f"No caption found for scene {i}, skipping audio generation")
    
    # Verify all frames have audio
    frame_count = len(scenes_data)
    log.info(f"Expected {frame_count} audio files")
    
    # Check if all expected audio files exist
    missing_audio = []
    for i in range(frame_count):
        audio_path = os.path.join(audio_dir, f"frame_{i:03d}_audio.mp3")
        if not os.path.exists(audio_path):
            missing_audio.append(i)
            
            # Try to generate audio for missing frames
            for scene in scenes_data:
                if scene.get("frame_number") == i and "caption" in scene and scene["caption"]:
                    log.warning(f"Attempting to regenerate missing audio for frame {i}")
                    audio_path = os.path.join(audio_dir, f"frame_{i:03d}_audio.mp3")
                    result_path = generate_voice_for_caption(
                        caption=scene["caption"],
                        speaker=scene.get("speaker", "Narrator"),
                        output_path=audio_path,
                        api_key=api_key
                    )
                    if result_path:
                        scene["audio_path"] = result_path
                        log.info(f"Successfully regenerated audio for frame {i}")
                    break
    
    if missing_audio:
        log.warning(f"Missing audio for frames: {missing_audio}")
    else:
        log.info("All frames have audio files")
    
    return scenes_data

if __name__ == "__main__":
    # Test functionality
    test_caption = "The subtle undulations of the mycological meadow often lulled even the most anxious mycophile into a state of serene contemplation."
    test_speaker = "Narrator (calm, descriptive)"
    test_output = "test_audio.mp3"
    
    generate_voice_for_caption(test_caption, test_speaker, test_output)
