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
    
    # Test binary execution
    binary_executable = False
    if binary_exists:
        try:
            result = subprocess.run([whisper_binary, "--help"], 
                                  capture_output=True, text=True, timeout=5)
            binary_executable = result.returncode == 0
        except:
            binary_executable = False
    
    return {
        "status": "healthy" if binary_exists and model_exists and binary_executable else "unhealthy",
        "model": "ggml-small.bin",
        "binary_exists": binary_exists,
        "model_exists": model_exists,
        "binary_executable": binary_executable,
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
    
    # Generate output file path without extension
    output_base = temp_file_path.rsplit('.', 1)[0]
    json_file_path = output_base + ".json"
    
    logger.info(f"Processing file: {file.filename}, temp path: {temp_file_path}")
    logger.info(f"Expected JSON output: {json_file_path}")

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
        
        # Build command - REMOVED -v flag and added proper output file flag
        cmd = [
            whisper_binary,
            "-f", temp_file_path,
            "-m", model_path,
            "-oj",  # Output JSON
            "-of", output_base,  # Output file base (without extension)
            "-t", "4",  # Threads
            "-l", "auto",  # Language auto-detect (use -l instead of --language)
            "--no-prints"  # Reduce noise in output
        ]
        
        logger.info(f"Executing command: {' '.join(cmd)}")
        
        # Execute whisper.cpp with extended timeout
        file_size_mb = os.path.getsize(temp_file_path) / (1024 * 1024)
        timeout_seconds = min(7200, max(300, int(file_size_mb * 60)))
        logger.info(f"File size: {file_size_mb:.1f}MB, timeout: {timeout_seconds}s")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        
        logger.info(f"Whisper exit code: {result.returncode}")
        if result.stdout:
            logger.info(f"Whisper stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"Whisper stderr: {result.stderr}")
        
        if result.returncode != 0:
            # Log more details for debugging
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Working directory: {os.getcwd()}")
            logger.error(f"Temp file exists: {os.path.exists(temp_file_path)}")
            logger.error(f"Temp file size: {os.path.getsize(temp_file_path)} bytes")
            
            raise HTTPException(
                status_code=500, 
                detail=f"Whisper processing failed (exit code {result.returncode}). stderr: {result.stderr[:500]}"
            )
        
        # Check for JSON output file
        if not os.path.exists(json_file_path):
            # List all files in temp directory to debug
            temp_dir = os.path.dirname(temp_file_path)
            available_files = os.listdir(temp_dir)
            logger.error(f"JSON file not found at {json_file_path}")
            logger.error(f"Available files in {temp_dir}: {available_files}")
            
            # Try to find any JSON file with similar name
            temp_basename = os.path.basename(temp_file_path).rsplit('.', 1)[0]
            potential_json_files = [f for f in available_files if f.endswith('.json') and temp_basename in f]
            
            if potential_json_files:
                json_file_path = os.path.join(temp_dir, potential_json_files[0])
                logger.info(f"Found alternative JSON file: {json_file_path}")
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"JSON output not found. Expected: {json_file_path}. Available: {available_files}"
                )

        # Read and parse JSON output
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
                logger.info(f"JSON file size: {len(json_content)} characters")
                json_output = json.loads(json_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON. First 500 chars: {json_content[:500]}")
            raise HTTPException(status_code=500, detail=f"Invalid JSON output: {str(e)}")
        
        logger.info(f"Successfully parsed JSON with keys: {list(json_output.keys())}")
        
        # Extract transcription segments
        segments = json_output.get("transcription", [])
        if not segments:
            # Try alternative keys
            segments = json_output.get("segments", [])
        
        # Extract text from segments
        if segments:
            full_text = " ".join([
                segment.get("text", "") for segment in segments
            ]).strip()
        else:
            # Fallback: try to get text directly
            full_text = json_output.get("text", "").strip()

        # Extract detected language
        detected_language = "unknown"
        if "language" in json_output:
            lang_info = json_output["language"]
            if isinstance(lang_info, dict):
                detected_language = lang_info.get("language", "unknown")
            elif isinstance(lang_info, str):
                detected_language = lang_info

        return {
            "success": True,
            "transcription": segments,
            "text": full_text,
            "language": detected_language,
            "model": "ggml-small.bin",
            "filename": file.filename,
            "debug": {
                "json_keys": list(json_output.keys()),
                "segments_count": len(segments)
            }
        }

    except subprocess.TimeoutExpired:
        logger.error("Transcription process timed out")
        raise HTTPException(status_code=408, detail=f"Transcription timed out after {timeout_seconds} seconds")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON output: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        # Cleanup temporary files
        cleanup_files = [temp_file_path, json_file_path]
        for file_path in cleanup_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {file_path}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
