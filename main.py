import os
import asyncio
import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import geminigen
from pathlib import Path

app = FastAPI()

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Create directories if they don't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# Store all generation results
generation_results = []

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(None),
    sequence_amount: int = Form(5),
    generate_videos: bool = Form(False),
    voice_id: str = Form("pNInz6obpgDQGcFmaJgB"),
    background_music: str = Form(None),
    background_music_volume: float = Form(0.5)
):
    # Log the received parameters
    print(f"DEBUG - Received background_music: {background_music}")
    print(f"DEBUG - Received background_music_volume: {background_music_volume}")
    
    # Create a new result entry
    new_result = {
        "id": len(generation_results) + 1,
        "status": "running",
        "output_dir": "",
        "video_path": "",
        "final_video_path": "",
        "error": "",
        "timestamp": asyncio.get_event_loop().time()
    }
    
    # Add to results list
    generation_results.insert(0, new_result)
    
    # Run the generation in the background
    background_tasks.add_task(run_generation, new_result, prompt, sequence_amount, generate_videos, voice_id, background_music, background_music_volume)
    
    return {"status": "started", "id": new_result["id"]}

async def run_generation(
    result, 
    prompt, 
    sequence_amount, 
    generate_videos,
    voice_id,
    background_music,
    background_music_volume
):
    try:
        # Check environment variables
        geminigen.check_environment_variables()
        
        # Run the generator
        await geminigen.async_main(
            generate_videos=generate_videos,
            custom_description=prompt,
            sequence_amount=sequence_amount,
            voice_id=voice_id,
            background_music_url=background_music,
            background_music_volume=background_music_volume
        )
        
        # Find the latest output directory
        base_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
        output_dirs = sorted([d for d in os.listdir(base_output_dir) if d.startswith("run_")], reverse=True)
        
        if output_dirs:
            latest_dir = os.path.join(base_output_dir, output_dirs[0])
            
            # Update results
            result["status"] = "completed"
            result["output_dir"] = latest_dir
            
            # Find video path
            video_path = os.path.join(latest_dir, "animation.mp4")
            if os.path.exists(video_path):
                result["video_path"] = os.path.relpath(video_path, start=os.path.dirname(os.path.abspath(__file__)))
            
            # Find final video path if videos were generated
            if generate_videos:
                final_video_path = os.path.join(latest_dir, "final_animation.mp4")
                if os.path.exists(final_video_path):
                    result["final_video_path"] = os.path.relpath(final_video_path, start=os.path.dirname(os.path.abspath(__file__)))
        else:
            result["status"] = "error"
            result["error"] = "No output directory found"
            
    except Exception as e:
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
