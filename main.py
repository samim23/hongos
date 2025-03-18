import os
import asyncio
import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks, Body, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import geminigen
from pathlib import Path
import shutil
import uuid

app = FastAPI()

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Create directories if they don't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("uploads", exist_ok=True)  # New directory for uploaded images

# Store all generation results
generation_results = []

# Store uploaded image paths
uploaded_images = {}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    # Generate a unique ID for this upload
    upload_id = str(uuid.uuid4())
    
    # Create file path
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join("uploads", f"{upload_id}{file_extension}")
    
    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Store the file path
    uploaded_images[upload_id] = {
        "path": file_path,
        "filename": file.filename
    }
    
    return {"upload_id": upload_id, "filename": file.filename}

@app.post("/clear-image/{upload_id}")
async def clear_image(upload_id: str):
    if upload_id in uploaded_images:
        # Delete the file if it exists
        file_path = uploaded_images[upload_id]["path"]
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from dictionary
        del uploaded_images[upload_id]
        
        return {"status": "success"}
    
    return {"status": "error", "message": "Image not found"}

@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(None),
    sequence_amount: int = Form(5),
    generate_videos: bool = Form(False),
    voice_id: str = Form("pNInz6obpgDQGcFmaJgB"),
    background_music: str = Form(None),
    background_music_volume: float = Form(0.5),
    initial_image_id: str = Form(None),
    video_model: str = Form("fal-ai/veo2/image-to-video")
):
    # Log the received parameters
    print(f"DEBUG - Received background_music: {background_music}")
    print(f"DEBUG - Received background_music_volume: {background_music_volume}")
    print(f"DEBUG - Received initial_image_id: {initial_image_id}")
    print(f"DEBUG - Received video_model: {video_model}")
    
    # Get the initial image path if provided
    initial_image_path = None
    if initial_image_id and initial_image_id in uploaded_images:
        initial_image_path = uploaded_images[initial_image_id]["path"]
        print(f"DEBUG - Using initial image: {initial_image_path}")
    
    # Create a new result entry
    new_result = {
        "id": len(generation_results) + 1,
        "status": "running",
        "output_dir": "",
        "video_path": "",
        "final_video_path": "",
        "error": "",
        "timestamp": asyncio.get_event_loop().time(),
        "initial_image_id": initial_image_id
    }
    
    # Add to results list
    generation_results.insert(0, new_result)
    
    # Run the generation in the background
    background_tasks.add_task(
        run_generation, 
        new_result, 
        prompt, 
        sequence_amount, 
        generate_videos, 
        voice_id, 
        background_music, 
        background_music_volume,
        initial_image_path,
        video_model
    )
    
    return {"status": "started", "id": new_result["id"]}

async def run_generation(
    result, 
    prompt, 
    sequence_amount, 
    generate_videos,
    voice_id,
    background_music,
    background_music_volume,
    initial_image_path,
    video_model
):
    try:
        # Add more detailed logging
        print(f"DEBUG - Starting generation with parameters:")
        print(f"  - prompt: {prompt[:50] if prompt else 'None'}...")
        print(f"  - sequence_amount: {sequence_amount}")
        print(f"  - generate_videos: {generate_videos}")
        print(f"  - voice_id: {voice_id}")
        print(f"  - background_music: {background_music}")
        print(f"  - background_music_volume: {background_music_volume}")
        print(f"  - initial_image_path: {initial_image_path}")
        print(f"  - video_model: {video_model}")
        
        # Check if the initial image exists
        if initial_image_path:
            # Convert to absolute path if it's not already
            if not os.path.isabs(initial_image_path):
                initial_image_path = os.path.abspath(initial_image_path)
                print(f"DEBUG - Converted to absolute path: {initial_image_path}")
            
            if os.path.exists(initial_image_path):
                print(f"DEBUG - Initial image exists at {initial_image_path}")
                # Get file size and dimensions for debugging
                file_size = os.path.getsize(initial_image_path)
                try:
                    from PIL import Image
                    img = Image.open(initial_image_path)
                    dimensions = img.size
                    print(f"DEBUG - Image size: {file_size} bytes, dimensions: {dimensions}")
                except Exception as e:
                    print(f"DEBUG - Error getting image info: {e}")
            else:
                print(f"ERROR - Initial image does not exist at {initial_image_path}")
                initial_image_path = None
        
        # Check environment variables
        geminigen.check_environment_variables()
        
        # Run the generator
        output_dir = await geminigen.async_main(
            generate_videos=generate_videos,
            custom_description=prompt,
            sequence_amount=sequence_amount,
            voice_id=voice_id,
            background_music_url=background_music,
            background_music_volume=background_music_volume,
            initial_image_path=initial_image_path,
            videogen_model=video_model
        )
        
        # If output_dir is None, try to find the most recent output directory
        if output_dir is None:
            print("DEBUG - Output directory not returned, trying to find the most recent one")
            try:
                base_output_dir = "outputs"
                if os.path.exists(base_output_dir) and os.path.isdir(base_output_dir):
                    # Get all run directories
                    run_dirs = [d for d in os.listdir(base_output_dir) if d.startswith("run_")]
                    if run_dirs:
                        # Sort by creation time (newest first)
                        run_dirs.sort(key=lambda x: os.path.getctime(os.path.join(base_output_dir, x)), reverse=True)
                        # Get the most recent directory
                        most_recent_dir = os.path.join(base_output_dir, run_dirs[0])
                        print(f"DEBUG - Found most recent output directory: {most_recent_dir}")
                        
                        # Check if this directory contains the expected files
                        if (os.path.exists(os.path.join(most_recent_dir, "animation.mp4")) or 
                            os.path.exists(os.path.join(most_recent_dir, "animation.gif"))):
                            output_dir = most_recent_dir
                            print(f"DEBUG - Using most recent output directory: {output_dir}")
            except Exception as e:
                print(f"DEBUG - Error finding most recent output directory: {e}")
        
        # Update result with output directory
        if output_dir:
            result["output_dir"] = output_dir
            result["status"] = "completed"
            
            # Find the video file
            video_path = os.path.join(output_dir, "animation.mp4")
            if os.path.exists(video_path):
                result["video_path"] = video_path
                print(f"DEBUG - Found video at {video_path}")
            else:
                print(f"WARNING - Video file not found at {video_path}")
            
            # Find the final video file if it exists
            final_video_path = os.path.join(output_dir, "final_video.mp4")
            if os.path.exists(final_video_path):
                result["final_video_path"] = final_video_path
                print(f"DEBUG - Found final video at {final_video_path}")
        else:
            result["status"] = "error"
            result["error"] = "Generation failed - no output directory returned"
            print("ERROR - No output directory found or returned")
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error\n{str(e)}\n\nDetails:\n{error_details}")
        result["status"] = "error"
        result["error"] = str(e)

@app.post("/process-folder/{folder_id}")
async def process_folder(
    folder_id: int, 
    background_tasks: BackgroundTasks,
    voice_id: str = Form("pNInz6obpgDQGcFmaJgB"),  # Updated default to Adam
    background_music: str = Form(None),
    background_music_volume: float = Form(0.5)
):
    # Find the result with the given ID
    result = None
    for r in generation_results:
        if r.get("id") == folder_id:
            result = r
            break
    
    if not result or not result.get("output_dir") or not os.path.exists(result["output_dir"]):
        return {"status": "error", "message": "Folder not found"}
    
    # Create a processing status
    result["processing_status"] = "running"
    
    # Run the processing in the background
    background_tasks.add_task(run_folder_processing, result, voice_id, background_music, background_music_volume)
    
    return {"status": "processing"}

async def run_folder_processing(
    result, 
    voice_id,
    background_music,
    background_music_volume
):
    try:
        # Process the folder
        await geminigen.process_existing_folder(
            result["output_dir"],
            voice_id=voice_id,
            background_music_url=background_music,
            background_music_volume=background_music_volume
        )
        
        # Update result
        result["processing_status"] = "completed"
    except Exception as e:
        # Update result with error
        result["processing_status"] = "error"
        result["processing_error"] = str(e)

@app.get("/status")
async def get_status():
    return generation_results

@app.get("/api-keys-status")
async def get_api_keys_status():
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    fal_key = os.environ.get("FAL_KEY", "")
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
    
    return {
        "gemini_key_set": bool(gemini_key),
        "fal_key_set": bool(fal_key),
        "elevenlabs_key_set": bool(elevenlabs_key),
        "gemini_key": gemini_key if gemini_key else "",
        "fal_key": fal_key if fal_key else "",
        "elevenlabs_key": elevenlabs_key if elevenlabs_key else ""
    }

@app.post("/set-api-key")
async def set_api_key(data: dict = Body(...)):
    key_type = data.get("key_type")
    api_key = data.get("api_key")
    
    if not key_type or not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing key_type or api_key"})
    
    if key_type == "gemini":
        os.environ["GEMINI_API_KEY"] = api_key
        return {"status": "success", "message": "Gemini API key set successfully"}
    elif key_type == "fal":
        os.environ["FAL_KEY"] = api_key
        return {"status": "success", "message": "FAL API key set successfully"}
    elif key_type == "elevenlabs":
        os.environ["ELEVENLABS_API_KEY"] = api_key
        return {"status": "success", "message": "ElevenLabs API key set successfully"}
    else:
        return JSONResponse(status_code=400, content={"error": "Invalid key_type"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
