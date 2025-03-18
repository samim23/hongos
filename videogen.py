# videogen.py
# pip install fal-client requests

import os
import sys
import argparse
import requests
import fal_client
import base64
import asyncio
from pathlib import Path

def encode_image_to_base64(image_path):
    """Convert a local image to base64 data URI"""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Get the file extension and determine content type
        file_ext = Path(image_path).suffix.lower()
        content_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }.get(file_ext, 'image/jpeg')
        
        return f"data:{content_type};base64,{encoded_string}"

async def upload_image_to_fal(image_path):
    """Upload a local image to FAL and return the URL"""
    return await fal_client.upload_file_async(image_path)

def download_video(url, output_path):
    """Download a video from a URL to a local file"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    return output_path

async def generate_video(image_path, prompt, output_dir=None, aspect_ratio="auto", duration="5s", use_upload=True, videogen_model="fal-ai/veo2/image-to-video"):
    """
    Generate a video from a local image using FAL API
    
    Args:
        image_path: Path to the local image
        prompt: Text prompt describing how to animate the image
        output_dir: Directory to save the output video (default: same as image)
        aspect_ratio: Aspect ratio of the output video (auto, 16:9, 9:16)
        duration: Duration of the output video (5s, 6s, 7s, 8s)
        use_upload: Whether to upload the image or use base64 encoding
        videogen_model: FAL model to use for video generation (default: fal-ai/veo2/image-to-video)
    
    Returns:
        Path to the downloaded video
    """
    # Check if image exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Determine output directory
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(image_path))
    os.makedirs(output_dir, exist_ok=True)
    
    # Get image URL (either by uploading or encoding)
    if use_upload:
        print(f"Uploading image: {image_path}")
        image_url = await upload_image_to_fal(image_path)
        print(f"Image uploaded to: {image_url}")
    else:
        print(f"Encoding image: {image_path}")
        image_url = encode_image_to_base64(image_path)
        print("Image encoded as data URI")
    
    # Generate video
    print(f"Generating video with prompt: '{prompt}'")
    
    # Submit the request using the async API
    handler = await fal_client.submit_async(
        videogen_model,
        arguments={
            "prompt": prompt,
            "image_url": image_url,
            "aspect_ratio": aspect_ratio,
            "duration": duration
        },
    )
    
    # Print progress logs
    async for event in handler.iter_events(with_logs=True):
        if hasattr(event, 'logs') and event.logs:
            for log in event.logs:
                print(f"Progress: {log['message']}")
    
    # Get the final result
    result = await handler.get()
    
    # Get video URL
    video_url = result["video"]["url"]
    print(f"Video generated: {video_url}")
    
    # Download video
    output_filename = f"{Path(image_path).stem}_animated.mp4"
    output_path = os.path.join(output_dir, output_filename)
    
    print(f"Downloading video to: {output_path}")
    download_video(video_url, output_path)
    print(f"Video downloaded to: {output_path}")
    
    return output_path

async def async_main(args):
    try:
        # Check if FAL_KEY is set
        if "FAL_KEY" not in os.environ:
            print("Error: FAL_KEY environment variable is not set")
            print("Please set it with: export FAL_KEY='your_api_key'")
            sys.exit(1)
        
        # Generate video
        output_path = await generate_video(
            args.image, 
            args.prompt,
            args.output_dir,
            args.aspect_ratio,
            args.duration,
            not args.use_base64,  # Invert the flag since our function uses use_upload
            args.videogen_model
        )
        
        print(f"\nSuccess! Video saved to: {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate videos from local images using FAL API")
    parser.add_argument("image", help="Path to the local image")
    parser.add_argument("prompt", help="Text prompt describing how to animate the image")
    parser.add_argument("--output-dir", help="Directory to save the output video")
    parser.add_argument("--aspect-ratio", choices=["auto", "16:9", "9:16"], default="auto", 
                        help="Aspect ratio of the output video")
    parser.add_argument("--duration", choices=["5s", "6s", "7s", "8s"], default="5s",
                        help="Duration of the output video")
    parser.add_argument("--use-base64", action="store_true", 
                        help="Use base64 encoding instead of uploading the image")
    parser.add_argument("--videogen-model", 
                        choices=["fal-ai/veo2/image-to-video", "fal-ai/luma-dream-machine/ray-2-flash/image-to-video"],
                        default="fal-ai/veo2/image-to-video",
                        help="Video generation model to use")
    
    args = parser.parse_args()
    
    # Run the async main function
    asyncio.run(async_main(args))

if __name__ == "__main__":
    main()