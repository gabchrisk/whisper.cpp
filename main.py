from fastapi import FastAPI, UploadFile, File, HTTPException
import subprocess
import os
import tempfile
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper.cpp API", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Whisper.cpp API is running", "endpoints": ["/transcribe"]}

@app.get("/health")
async def health_check():
    # Verify binary and model exist
    whisper_binary = "/app/whisper.cpp/build/whisper-cli"
    model_path = "/app/models/ggml-small.bin"
    
    binary_exists = os.path.exists(whisper_binary)
    model_exists = os.path.exists(model_path)
    
    return {
        "status": "healthy" if binary_exists and model_exists else "unhealthy",
        "model": "ggml-small.bin",
        "binary_exists": binary_exists,
        "model_exists": model_exists,
        "binary_path": whisper_binary,
        "model_path": model_path
    }

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # Validate file type
    allowed_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4', '.avi', '.mov']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file_path = temp_file.name
        content = await file.read()
        temp_file.write(content)
    
    json_file_path = temp_file_path + ".json"
    
    logger.info(f"Processing file: {file.filename}, temp path: {temp_file_path}")

    try:
        # Verify paths
        whisper_binary = "/app/whisper.cpp/build/whisper-cli"
        model_path = "/app/models/ggml-small.bin"
        
        if not os.path.exists(whisper_binary):
            raise HTTPException(status_code=500, detail=f"Whisper binary not found at {whisper_binary}")
        if not os.path.exists(model_path):
            raise HTTPException(status_code=500, detail=f"Whisper model not found at {model_path}")
        
        # Check if binary is executable
        if not os.access(whisper_binary, os.X_OK):
            raise HTTPException(status_code=500, detail=f"Whisper binary is not executable: {whisper_binary}")
        
        # Build command
        cmd = [
            whisper_binary,
            "-f", temp_file_path,
            "-m", model_path,
            "-oj",  # Output JSON to file
            "-t", "4",  # Threads
            "--language", "auto",  # Auto-detect language
            "-v"  # Verbose output for debugging
        ]
        
        logger.info(f"Executing command: {' '.join(cmd)}")
        
        # Execute whisper.cpp with extended timeout for long recordings
        # Scale timeout: minimum 5 minutes, up to 2 hours for very large files
        file_size_mb = os.path.getsize(temp_file_path) / (1024 * 1024)
        timeout_seconds = min(7200, max(300, int(file_size_mb * 60)))  # ~1 minute per MB
        logger.info(f"File size: {file_size_mb:.1f}MB, estimated timeout: {timeout_seconds}s ({timeout_seconds//60}min)")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        
        logger.info(f"Whisper exit code: {result.returncode}")
        logger.info(f"Whisper stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"Whisper stderr: {result.stderr}")
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, 
                detail=f"Whisper processing failed (exit code {result.returncode}): {result.stderr}"
            )
        
        # Check for JSON output file
        if not os.path.exists(json_file_path):
            # Try alternative JSON file locations
            alt_json_paths = [
                temp_file_path.rsplit('.', 1)[0] + '.json',  # Without original extension
                os.path.join(os.path.dirname(temp_file_path), 
                           os.path.basename(temp_file_path).rsplit('.', 1)[0] + '.json')
            ]
            
            json_found = False
            for alt_path in alt_json_paths:
                if os.path.exists(alt_path):
                    json_file_path = alt_path
                    json_found = True
                    logger.info(f"Found JSON output at alternative path: {alt_path}")
                    break
            
            if not json_found:
                raise HTTPException(
                    status_code=500,
                    detail=f"JSON output file not found. Expected: {json_file_path}. Available files: {os.listdir(os.path.dirname(temp_file_path))}"
                )

        # Read and parse JSON output
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_output = json.load(f)
        
        logger.info(f"Successfully parsed JSON output with {len(json_output.get('transcription', []))} segments")
        
        # Extract text from segments
        full_text = " ".join([
            segment.get("text", "") for segment in json_output.get("transcription", [])
        ]).strip()

        # Extract detected language
        detected_language = "unknown"
        if isinstance(json_output.get("language"), dict):
            detected_language = json_output["language"].get("language", "unknown")
        elif isinstance(json_output.get("language"), str):
            detected_language = json_output["language"]

        return {
            "success": True,
            "transcription": json_output.get("transcription", []),
            "text": full_text,
            "language": detected_language,
            "model": "ggml-small.bin",
            "filename": file.filename
        }

    except subprocess.TimeoutExpired:
        logger.error("Transcription process timed out")
        raise HTTPException(status_code=408, detail="Transcription process timed out after 5 minutes.")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON output: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # Cleanup temporary files
        for file_path in [temp_file_path, json_file_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {file_path}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
