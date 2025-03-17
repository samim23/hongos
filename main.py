import os
import asyncio
import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks
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
    custom_description: str = Form(""),
    sequence_amount: int = Form(5),
    generate_videos: bool = Form(False)
):
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
    background_tasks.add_task(run_generation, new_result, custom_description, sequence_amount, generate_videos)
    
    return {"status": "started", "id": new_result["id"]}

async def run_generation(result, custom_description, sequence_amount, generate_videos):
    try:
        # Check environment variables
        geminigen.check_environment_variables()
        
        # Run the generator
        await geminigen.async_main(
            generate_videos=generate_videos,
            custom_description=custom_description,
            sequence_amount=sequence_amount
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
async def process_folder(folder_id: int, background_tasks: BackgroundTasks):
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
    background_tasks.add_task(run_folder_processing, result)
    
    return {"status": "processing"}

async def run_folder_processing(result):
    try:
        folder_path = result["output_dir"]
        await geminigen.process_existing_folder(folder_path)
        
        # Update the result with the new video path
        final_video_path = os.path.join(folder_path, "final_animation.mp4")
        if os.path.exists(final_video_path):
            result["final_video_path"] = os.path.relpath(final_video_path, start=os.path.dirname(os.path.abspath(__file__)))
            result["processing_status"] = "completed"
        else:
            result["processing_status"] = "error"
            result["processing_error"] = "Failed to generate final video"
    except Exception as e:
        result["processing_status"] = "error"
        result["processing_error"] = str(e)

@app.get("/status")
async def get_status():
    return generation_results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
