"""Generator module for the Gemini GIF Generator."""

import os
import time
import logging
import subprocess
from io import BytesIO
from PIL import Image
from tqdm import tqdm
from google import genai
from google.genai import types
import json
import re
from datetime import datetime

# Import voice generation module
from voicegen import generate_voices_for_scenes

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# API keys
GEMINI_API_KEY = "AIzaSyC7ddAPsaxtDv-Yisu_w4iNrLtSgmrpqpo"  # Replace with your API key
ELEVENLABS_API_KEY = "sk_5067d1b46bdf4b8acf00671004da5d8796ba8bf2dff6b287"  # Replace with your ElevenLabs API key

def initialize_client(api_key):
    """Initialize the Gemini client."""
    return genai.Client(api_key=api_key)

def generate_frames(client, prompt, model="models/gemini-2.0-flash-exp", max_retries=3):
    """Generate animation frames with retry logic if only one frame is returned."""
    # Create a progress bar for the generation attempts
    pbar = tqdm(total=max_retries, desc="Generating frames", unit="attempt")
    
    for attempt in range(1, max_retries + 1):
        log.info(f"Attempt {attempt}/{max_retries}: Sending request to Gemini with prompt: {prompt}")
        
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=['Text', 'Image'])
            )
            
            # Count the number of image frames
            frame_count = 0
            
            # Add more detailed logging about the response structure
            log.info(f"Response type: {type(response)}")
            log.info(f"Response attributes: {dir(response)}")
            
            if hasattr(response, 'candidates') and response.candidates:
                log.info(f"Number of candidates: {len(response.candidates)}")
                
                # Check if the first candidate has content
                if hasattr(response.candidates[0], 'content'):
                    log.info(f"Content attributes: {dir(response.candidates[0].content)}")
                    
                    # Check if content has parts
                    if hasattr(response.candidates[0].content, 'parts'):
                        log.info(f"Number of parts: {len(response.candidates[0].content.parts)}")
                        
                        for part in response.candidates[0].content.parts:
                            log.info(f"Part type: {type(part)}")
                            if hasattr(part, 'inline_data') and part.inline_data is not None:
                                frame_count += 1
                                log.info(f"Found image data in part {frame_count}")
            
            log.info(f"Received {frame_count} frames in response")
            
            # If we got multiple frames, return the response
            if frame_count > 1:
                log.info(f"Successfully received {frame_count} frames on attempt {attempt}")
                pbar.update(max_retries - pbar.n)  # Complete the progress bar
                pbar.close()
                return response
            
            # If this was the last attempt, return what we have
            if attempt == max_retries:
                log.warning(f"Failed to get multiple frames after {max_retries} attempts. Proceeding with {frame_count} frames.")
                pbar.update(1)
                pbar.close()
                return response
            
            # Otherwise, try again with a stronger prompt
            log.warning(f"Only received {frame_count} frame(s). Retrying with enhanced prompt...")
            prompt = f"{prompt} Please create at least 5 distinct frames showing different stages of the animation."
            time.sleep(1)  # Small delay between retries
            
            pbar.update(1)
            
        except Exception as e:
            log.error(f"Error generating frames: {str(e)}")
            if attempt == max_retries:
                pbar.close()
                raise
            time.sleep(2)  # Longer delay after an error
            pbar.update(1)
    
    # This should not be reached, but just in case
    pbar.close()
    raise RuntimeError("Failed to generate frames after maximum retries")

def extract_scene_info_with_llm(client, text_parts, output_dir):
    """Use the LLM to extract scene information from text parts."""
    
    # Combine all text parts
    combined_text = "\n\n".join([part for part in text_parts if part])
    
    # Create a prompt for the LLM to extract structured information
    extraction_prompt = f"""
    Below is text describing scenes from a TV ad. For each scene, extract:
    1. Scene number
    2. Visual description
    3. Caption
    4. Speaker (infer who would be speaking the caption based on the scene description)

    For the speaker field, provide details like gender, age, character type, or emotional state.
    Examples: "Character 1 (man, nervous)", "Narrator (female, authoritative)", "Mushroom mascot (cheerful)"

    Format the output as a JSON array where each object has the structure:
    {{
      "scene_number": (integer),
      "visual_description": (string),
      "caption": (string),
      "speaker": (string)
    }}
    
    Only include the JSON in your response, nothing else.
    
    TEXT TO PROCESS:
    {combined_text}
    """
    
    try:
        # Send the extraction request to the LLM
        extraction_response = client.models.generate_content(
            model="models/gemini-1.5-pro",  # Using a text-focused model
            contents=extraction_prompt
        )
        
        # Get the response text
        if extraction_response and hasattr(extraction_response, 'candidates') and extraction_response.candidates:
            json_text = extraction_response.candidates[0].content.parts[0].text
            
            # Try to parse the JSON
            try:
                # Clean up the text to ensure it's valid JSON
                json_text = json_text.strip()
                if json_text.startswith("```json"):
                    json_text = json_text.split("```json")[1]
                if json_text.endswith("```"):
                    json_text = json_text.split("```")[0]
                
                json_text = json_text.strip()
                
                # Parse the JSON
                scenes_info = json.loads(json_text)
                
                # Save the raw LLM response for debugging
                with open(os.path.join(output_dir, "llm_extraction_response.txt"), 'w') as f:
                    f.write(json_text)
                
                return scenes_info
            except json.JSONDecodeError as e:
                log.error(f"Error parsing JSON from LLM response: {str(e)}")
                log.error(f"Raw response: {json_text}")
                
                # Save the problematic response for debugging
                with open(os.path.join(output_dir, "failed_llm_extraction.txt"), 'w') as f:
                    f.write(json_text)
                
                return None
        else:
            log.error("No valid response from LLM for scene extraction")
            return None
    except Exception as e:
        log.error(f"Error using LLM to extract scene info: {str(e)}")
        return None

def extract_scene_info(text):
    """Extract scene information using regex as a fallback."""
    # Default empty scene info
    scene_info = {
        "scene_number": 0,
        "visual_description": "",
        "caption": "",
        "speaker": "Narrator"
    }
    
    # Try to extract scene number
    scene_match = re.search(r"SCENE\s+(\d+)", text, re.IGNORECASE)
    if scene_match:
        scene_info["scene_number"] = int(scene_match.group(1))
    
    # Try to extract caption (assuming it's a single line that looks like a caption)
    caption_match = re.search(r'"([^"]+)"', text)
    if caption_match:
        scene_info["caption"] = caption_match.group(1)
    else:
        # Alternative: look for sentences that might be captions
        sentences = re.findall(r'([A-Z][^.!?]*[.!?])', text)
        if sentences:
            # Use the shortest sentence as the caption (often captions are concise)
            scene_info["caption"] = min(sentences, key=len)
    
    return scene_info

def create_video_with_audio(frame_paths, scenes_info, output_dir):
    """
    Create a video from frames and audio files using MoviePy.
    
    Args:
        frame_paths (list): List of paths to frame images
        scenes_info (list): List of scene dictionaries with audio_path
        output_dir (str): Directory to save the output video
    
    Returns:
        str: Path to the output video file
    """
    log.info("Creating video from frames and audio using MoviePy...")
    
    try:
        # Import MoviePy
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
        
        # Output video path
        video_path = os.path.join(output_dir, "animation.mp4")
        
        # Create clips for each frame with its audio
        clips = []
        
        for i, scene in enumerate(scenes_info):
            if i >= len(frame_paths):
                continue  # Skip if we don't have a frame for this scene
                
            frame_path = frame_paths[i]
            
            # Check if we have audio for this scene
            audio_path = scene.get("audio_path", None)
            
            if audio_path and os.path.exists(audio_path):
                # Create image clip
                image_clip = ImageClip(frame_path)
                
                # Load audio
                audio_clip = AudioFileClip(audio_path)
                
                # Set duration of image clip to match audio
                image_clip = image_clip.set_duration(audio_clip.duration)
                
                # Set audio
                image_clip = image_clip.set_audio(audio_clip)
                
                clips.append(image_clip)
                log.info(f"Created clip {i+1} with audio (duration: {audio_clip.duration:.2f}s)")
            else:
                # No audio, create a silent clip
                image_clip = ImageClip(frame_path).set_duration(3)  # 3 seconds default
                clips.append(image_clip)
                log.info(f"Created clip {i+1} without audio (duration: 3.00s)")
        
        if clips:
            # Concatenate all clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Write output file
            final_clip.write_videofile(
                video_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=os.path.join(output_dir, "temp_audio.m4a"),
                remove_temp=True
            )
            
            # Close clips to free resources
            for clip in clips:
                clip.close()
            final_clip.close()
            
            log.info(f"Successfully created video with audio at {video_path}")
        else:
            log.error("No clips were created successfully")
            return None
        
        return video_path
    except Exception as e:
        log.error(f"Error creating video with MoviePy: {str(e)}")
        return None

def main():
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
    output_dir = os.path.join(base_output_dir, f"run_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    log.info(f"Using output directory at {output_dir}")
    
    # Initialize client
    client = initialize_client(GEMINI_API_KEY)
    
    # Define prompt with enhanced instructions for character information
    prompt = """GENERATE (do not describe) a sequence of 5-8 actual images.
    Each image should be a frame in a TV ad for a mushroom supplement company.
    Make it ULTRA FUNNY and absurd in a Wes Anderson style.
    Each generated image should be a different scene.
    
    IMPORTANT: For each image, please provide:
    1. SCENE X: (where X is the scene number)
    2. A detailed visual description of what's in the image
    3. A caption in Wes Anderson style
    Please return actual generated images, not just text descriptions."""
    
    try:
        # Generate frames
        response = generate_frames(client, prompt)
        
        # Process and save frames
        frame_paths = []
        frame_count = 0
        text_parts = []  # Collect all text parts
        
        if response and hasattr(response, 'candidates') and response.candidates:
            # First pass: collect all text and save all images
            for part_index, part in enumerate(response.candidates[0].content.parts):
                if hasattr(part, 'text') and part.text is not None:
                    log.info(f"Text content part {part_index + 1}: {part.text[:100]}...")
                    print(part.text)
                    text_parts.append(part.text)
                    
                elif hasattr(part, 'inline_data') and part.inline_data is not None:
                    try:
                        # Save the image to the outputs directory
                        frame_path = os.path.join(output_dir, f"frame_{frame_count:03d}.png")
                        from PIL import Image
                        from io import BytesIO
                        image = Image.open(BytesIO(part.inline_data.data))
                        image.save(frame_path)
                        frame_paths.append(frame_path)
                        
                        frame_count += 1
                        log.info(f"Saved frame {frame_count} to {frame_path}")
                    except Exception as e:
                        log.error(f"Error saving image: {str(e)}")
            
            # Second pass: use LLM to extract scene information
            scenes_info = extract_scene_info_with_llm(client, text_parts, output_dir)
            
            # If LLM extraction failed, fall back to regex
            if not scenes_info:
                log.warning("LLM extraction failed, falling back to regex extraction")
                scenes_info = []
                for i, frame_path in enumerate(frame_paths):
                    # Try to find corresponding text for this image
                    scene_info = extract_scene_info(text_parts[i] if i < len(text_parts) else "")
                    scene_info["image_path"] = frame_path
                    scene_info["frame_number"] = i
                    scenes_info.append(scene_info)
            else:
                # Add image paths to the LLM-extracted scene info
                for i, scene_info in enumerate(scenes_info):
                    if i < len(frame_paths):
                        scene_info["image_path"] = frame_paths[i]
                        scene_info["frame_number"] = i
            
            # Generate voice for each scene
            log.info("Generating voice audio for scenes...")
            scenes_info = generate_voices_for_scenes(scenes_info, output_dir, ELEVENLABS_API_KEY)
            
            # Save scenes data to JSON file
            json_path = os.path.join(output_dir, "scenes_data.json")
            with open(json_path, 'w') as f:
                json.dump(scenes_info, f, indent=2)
            log.info(f"Saved scene information to {json_path}")
        
        # Create GIF animation
        log.info(f"Found {len(frame_paths)} frames to process")
        
        # Create GIF animation with PIL
        gif_path = os.path.join(output_dir, "animation.gif")
        
        try:
            # Use PIL to create GIF
            from PIL import Image
            
            images = [Image.open(frame_path) for frame_path in frame_paths]
            
            # Save as GIF
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                optimize=False,
                duration=500,  # 500ms per frame
                loop=0
            )
            
            log.info(f"Animation successfully saved to {gif_path}")
        except Exception as e:
            log.error(f"Error creating GIF with PIL: {str(e)}")
        
        # Create MP4 video with audio - using MoviePy
        try:
            video_path = create_video_with_audio(frame_paths, scenes_info, output_dir)
            if video_path:
                log.info(f"Video with audio successfully saved to {video_path}")
        except Exception as e:
            log.error(f"Error creating video with audio: {str(e)}")
        
        print(f"\nOutput files saved to: {output_dir}")
        print(f"GIF animation: {gif_path}")
        if 'video_path' in locals() and video_path:
            print(f"Video with audio: {video_path}")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()