"""Generator module for the Gemini GIF Generator."""

import os
import time
import logging
import subprocess
import argparse
import asyncio
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
# Import video generation module
import videogen

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# API keys
GEMINI_API_KEY = "AIzaSyC7ddAPsaxtDv-Yisu_w4iNrLtSgmrpqpo"  # Replace with your API key
ELEVENLABS_API_KEY = "sk_5067d1b46bdf4b8acf00671004da5d8796ba8bf2dff6b287"  # Replace with your ElevenLabs API key
FAL_KEY = "2f556b63-6b7e-4dd9-a6d7-6d708f2b5197:920e87577feda752aec2014358b8c25c" # Replace with your FAL API key

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
    Examples: "Character 1 (man, nervous)", "Narrator (female, authoritative)", "Mascot (cheerful)"

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
        
        for i, frame_path in enumerate(frame_paths):
            # Find the corresponding scene info
            scene = None
            for s in scenes_info:
                # Match by frame_number if available
                if "frame_number" in s and s["frame_number"] == i:
                    scene = s
                    break
                # Match by image_path if available
                elif "image_path" in s and os.path.basename(s["image_path"]) == os.path.basename(frame_path):
                    scene = s
                    break
            
            # If no matching scene found, use the scene at the same index if available
            if scene is None and i < len(scenes_info):
                scene = scenes_info[i]
                log.warning(f"No exact match found for frame {i}, using scene at index {i}")
            
            # Create image clip
            image_clip = ImageClip(frame_path)
            
            # Check if we have audio for this scene
            audio_path = None
            if scene and "audio_path" in scene and os.path.exists(scene["audio_path"]):
                audio_path = scene["audio_path"]
            
            if audio_path:
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
                image_clip = image_clip.set_duration(3)  # 3 seconds default
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

async def generate_video_prompt(client, scene_info):
    """Generate a prompt for video generation using LLM."""
    prompt_template = f"""
    Given this information, write a prompt for a "image+text to video" generation AI system. Keep the prompt very short and concise, as continuous text without heading etc. Focus on the action in the scene, camera, lightning:

    "visual_description": "{scene_info['visual_description']}",
    "caption": "{scene_info['caption']}", 
    """
    
    try:
        response = client.models.generate_content(
            model="models/gemini-1.5-pro",
            contents=prompt_template
        )
        
        if response and hasattr(response, 'candidates') and response.candidates:
            video_prompt = response.candidates[0].content.parts[0].text.strip()
            log.info(f"Generated video prompt: {video_prompt}")
            return video_prompt
        else:
            log.error("Failed to generate video prompt")
            return f"Animate this scene: {scene_info['caption']}"
    except Exception as e:
        log.error(f"Error generating video prompt: {str(e)}")
        return f"Animate this scene: {scene_info['caption']}"

async def generate_videos_for_frames(client, scenes_info, output_dir):
    """Generate videos for each frame using the FAL API."""
    log.info("Starting video generation for each frame...")
    
    # Set FAL API key in environment
    os.environ["FAL_KEY"] = FAL_KEY
    
    # Create videos directory
    videos_dir = os.path.join(output_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    
    # Track generated video paths
    video_paths = []
    
    # Process each scene
    for i, scene in enumerate(scenes_info):
        if "image_path" not in scene:
            log.warning(f"Scene {i+1} has no image path, skipping")
            continue
            
        image_path = scene["image_path"]
        
        # Generate video prompt using LLM
        video_prompt = await generate_video_prompt(client, scene)
        
        # Generate video
        try:
            log.info(f"Generating video for frame {i+1}...")
            video_output_path = await videogen.generate_video(
                image_path=image_path,
                prompt=video_prompt,
                output_dir=videos_dir,
                aspect_ratio="16:9",
                duration="5s",
                use_upload=True
            )
            
            # Add video path to scene info
            scene["video_path"] = video_output_path
            video_paths.append(video_output_path)
            
            log.info(f"Video generated for frame {i+1}: {video_output_path}")
        except Exception as e:
            log.error(f"Error generating video for frame {i+1}: {str(e)}")
    
    return video_paths

def combine_generated_videos(video_paths, scenes_info, output_dir):
    """Combine all generated videos into a single video with audio."""
    log.info("Combining all generated videos...")
    
    try:
        # Import MoviePy
        from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip
        
        # Output video path
        final_video_path = os.path.join(output_dir, "final_animation.mp4")
        
        # Create clips for each video
        clips = []
        
        for i, video_path in enumerate(video_paths):
            if not os.path.exists(video_path):
                log.warning(f"Video file not found: {video_path}, skipping")
                continue
                
            # Load video clip
            video_clip = VideoFileClip(video_path)
            
            # Check if we have audio for this scene
            if i < len(scenes_info) and "audio_path" in scenes_info[i] and os.path.exists(scenes_info[i]["audio_path"]):
                # Load audio
                audio_clip = AudioFileClip(scenes_info[i]["audio_path"])
                
                # Set duration of video clip to match audio if audio is longer
                if audio_clip.duration > video_clip.duration:
                    video_clip = video_clip.set_duration(audio_clip.duration)
                
                # Set audio
                video_clip = video_clip.set_audio(audio_clip)
                
                log.info(f"Added audio to video clip {i+1} (duration: {video_clip.duration:.2f}s)")
            
            clips.append(video_clip)
            log.info(f"Added video clip {i+1} (duration: {video_clip.duration:.2f}s)")
        
        if clips:
            # Concatenate all clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Write output file
            final_clip.write_videofile(
                final_video_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=os.path.join(output_dir, "temp_final_audio.m4a"),
                remove_temp=True
            )
            
            # Close clips to free resources
            for clip in clips:
                clip.close()
            final_clip.close()
            
            log.info(f"Successfully created final video at {final_video_path}")
            return final_video_path
        else:
            log.error("No video clips were created successfully")
            return None
    except Exception as e:
        log.error(f"Error combining videos: {str(e)}")
        return None

async def async_main(generate_videos=False):
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
    Make it ULTRA FUNNY and absurd in a Pedro Almodóvar style.
    Each generated image should be a different scene.
    
    IMPORTANT: For each image, please provide:
    1. SCENE X: (where X is the scene number)
    2. A detailed visual description of what's in the image
    3. A caption that fits the scene
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
                    scene_info["frame_number"] = i  # Explicitly set 0-based frame number
                    scenes_info.append(scene_info)
            else:
                # Add image paths to the LLM-extracted scene info
                for i, scene_info in enumerate(scenes_info):
                    if i < len(frame_paths):
                        scene_info["image_path"] = frame_paths[i]
                        scene_info["frame_number"] = i  # Explicitly set 0-based frame number
            
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
        
        # Generate videos for each frame if requested
        final_video_path = None
        if generate_videos:
            log.info("Video generation requested. Starting video generation process...")
            try:
                # Generate videos for each frame
                video_paths = await generate_videos_for_frames(client, scenes_info, output_dir)
                
                # Save updated scenes data with video paths
                with open(os.path.join(output_dir, "scenes_data_with_videos.json"), 'w') as f:
                    json.dump(scenes_info, f, indent=2)
                
                # Combine all videos into a final video
                if video_paths:
                    final_video_path = combine_generated_videos(video_paths, scenes_info, output_dir)
                    if final_video_path:
                        log.info(f"Final animated video successfully saved to {final_video_path}")
            except Exception as e:
                log.error(f"Error in video generation process: {str(e)}")
        
        print(f"\nOutput files saved to: {output_dir}")
        print(f"GIF animation: {gif_path}")
        if 'video_path' in locals() and video_path:
            print(f"Video with audio: {video_path}")
        if final_video_path:
            print(f"Final animated video: {final_video_path}")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")

async def process_existing_folder(folder_path):
    """Process an existing output folder to generate videos."""
    log.info(f"Processing existing folder: {folder_path}")
    
    # Check if the folder exists
    if not os.path.exists(folder_path):
        log.error(f"Folder not found: {folder_path}")
        return
    
    # Check for required files
    scenes_data_path = os.path.join(folder_path, "scenes_data.json")
    if not os.path.exists(scenes_data_path):
        log.error(f"scenes_data.json not found in {folder_path}")
        return
    
    # Load scenes data
    try:
        with open(scenes_data_path, 'r') as f:
            scenes_info = json.load(f)
        log.info(f"Loaded scene information from {scenes_data_path}")
    except Exception as e:
        log.error(f"Error loading scenes data: {str(e)}")
        return
    
    # Initialize client
    client = initialize_client(GEMINI_API_KEY)
    
    # Set FAL API key in environment
    os.environ["FAL_KEY"] = FAL_KEY
    
    # Find all frame files in the folder
    frame_files = sorted([f for f in os.listdir(folder_path) if f.startswith("frame_") and f.endswith(".png")])
    log.info(f"Found {len(frame_files)} frame files in folder")
    
    # Find all audio files in the folder
    audio_dir = os.path.join(folder_path, "audio")
    audio_files = []
    if os.path.exists(audio_dir):
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith(".mp3")])
        log.info(f"Found {len(audio_files)} audio files in folder")
    
    # Make sure scenes_info has entries for all frames
    if len(frame_files) > len(scenes_info):
        log.warning(f"Found more frames ({len(frame_files)}) than scenes in JSON ({len(scenes_info)})")
        # Add missing scenes
        for i in range(len(scenes_info), len(frame_files)):
            scenes_info.append({
                "scene_number": i + 1,
                "visual_description": f"Scene {i + 1}",
                "caption": f"Scene {i + 1}",
                "speaker": "Narrator",
                "frame_number": i
            })
    
    # Update image paths and audio paths for all scenes
    for i, frame_file in enumerate(frame_files):
        frame_path = os.path.join(folder_path, frame_file)
        if i < len(scenes_info):
            # Update image path
            scenes_info[i]["image_path"] = frame_path
            log.info(f"Set image path for scene {i+1}: {frame_path}")
            
            # Try to find matching audio file
            # First check if audio_path already exists and is valid
            if "audio_path" in scenes_info[i] and os.path.exists(scenes_info[i]["audio_path"]):
                log.info(f"Using existing audio path for scene {i+1}: {scenes_info[i]['audio_path']}")
            else:
                # Try to find by frame number (0-based) first
                frame_num = i
                audio_pattern = f"frame_{frame_num:03d}_audio.mp3"
                audio_path = os.path.join(audio_dir, audio_pattern)
                
                if os.path.exists(audio_path):
                    scenes_info[i]["audio_path"] = audio_path
                    log.info(f"Found audio for frame {frame_num}: {audio_path}")
                else:
                    # Try to find audio file by scene number (1-based) as fallback
                    scene_num = i + 1
                    audio_pattern = f"scene_{scene_num:03d}_audio.mp3"
                    audio_path = os.path.join(audio_dir, audio_pattern)
                    
                    if os.path.exists(audio_path):
                        scenes_info[i]["audio_path"] = audio_path
                        log.info(f"Found audio for scene {scene_num}: {audio_path}")
                    else:
                        log.warning(f"No audio found for frame {frame_num} / scene {scene_num}")
    
    # Generate videos for each frame
    try:
        log.info("Starting video generation for existing frames...")
        video_paths = await generate_videos_for_frames(client, scenes_info, folder_path)
        
        # Save updated scenes data with video paths
        with open(os.path.join(folder_path, "scenes_data_with_videos.json"), 'w') as f:
            json.dump(scenes_info, f, indent=2)
        
        # Combine all videos into a final video
        if video_paths:
            final_video_path = combine_generated_videos(video_paths, scenes_info, folder_path)
            if final_video_path:
                log.info(f"Final animated video successfully saved to {final_video_path}")
                print(f"\nFinal animated video: {final_video_path}")
            else:
                log.error("Failed to create final video")
        else:
            log.error("No videos were generated successfully")
    except Exception as e:
        log.error(f"Error in video generation process: {str(e)}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate animated TV ads with Gemini")
    parser.add_argument("--generate-videos", action="store_true", 
                        help="Generate animated videos for each frame (expensive and time-consuming)")
    parser.add_argument("--process-folder", type=str, 
                        help="Process an existing output folder to generate videos")
    
    args = parser.parse_args()
    
    if args.process_folder:
        # Process existing folder
        asyncio.run(process_existing_folder(args.process_folder))
    else:
        # Run the normal flow
        asyncio.run(async_main(args.generate_videos))

if __name__ == "__main__":
    main()