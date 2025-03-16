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
    
    # Process each scene
    for i, scene in enumerate(scenes_data):
        if "caption" in scene and scene["caption"]:
            # Generate filename
            scene_num = scene.get("scene_number", i+1)
            audio_filename = f"scene_{scene_num:03d}_audio.mp3"
            audio_path = os.path.join(audio_dir, audio_filename)
            
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
    
    return scenes_data

if __name__ == "__main__":
    # Test functionality
    test_caption = "The subtle undulations of the mycological meadow often lulled even the most anxious mycophile into a state of serene contemplation."
    test_speaker = "Narrator (calm, descriptive)"
    test_output = "test_audio.mp3"
    
    generate_voice_for_caption(test_caption, test_speaker, test_output)
