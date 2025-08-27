from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import subprocess
import os
import tempfile
import json

app = FastAPI(title="Whisper.cpp API", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Whisper.cpp API is running", "endpoints": ["/transcribe"]}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "ggml-small.bin"}

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
    
    try:
        # Path ke whisper.cpp binary
        whisper_binary = "/app/whisper.cpp/build/main"
        model_path = "/app/models/ggml-small.bin"
        
        # Check if files exist
        if not os.path.exists(whisper_binary):
            raise HTTPException(status_code=500, detail="Whisper binary not found")
        if not os.path.exists(model_path):
            raise HTTPException(status_code=500, detail="Whisper model not found")
        
        # Run whisper.cpp
        cmd = [
            whisper_binary,
            "-f", temp_file_path,
            "-m", model_path,
            "-oj",  # Output JSON format
            "-t", "4",  # Use 4 threads
            "--language", "auto"  # Auto detect language
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, 
                detail=f"Whisper processing failed: {result.stderr}"
            )
        
        # Parse output - whisper.cpp outputs to stdout
        transcription_text = result.stdout.strip()
        
        # Try to parse as JSON if possible, otherwise return as plain text
        try:
            # Look for JSON output file (whisper.cpp creates .json file)
            json_file = temp_file_path + ".json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_output = json.load(f)
                os.remove(json_file)  # Clean up
                
                return {
                    "success": True,
                    "transcription": json_output.get("transcription", []),
                    "text": " ".join([segment.get("text", "") for segment in json_output.get("transcription", [])]).strip(),
                    "language": json_output.get("language", "auto"),
                    "model": "ggml-small.bin",
                    "filename": file.filename
                }
            else:
                # Fallback to stdout
                return {
                    "success": True,
                    "text": transcription_text,
                    "model": "ggml-small.bin",
                    "filename": file.filename
                }
                
        except Exception as e:
            # If JSON parsing fails, return plain text
            return {
                "success": True,
                "text": transcription_text,
                "model": "ggml-small.bin",
                "filename": file.filename
            }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Transcription timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
