import logging
import os
import subprocess
import tempfile
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define paths for the model and binary
MODEL_PATH = "/app/models/ggml-small.bin"
WHISPER_BINARY_PATH = "/app/whisper.cpp/build/bin/main"

app = FastAPI(
    title="Whisper.cpp API",
    description="A simple API to run transcriptions using whisper.cpp",
    version="1.0.0"
)

@app.get("/", tags=["General"])
async def root():
    """Root endpoint to check if the API is running."""
    return {"message": "Whisper.cpp API is running. Use the /transcribe endpoint to process files."}

@app.get("/health", tags=["General"])
async def health_check():
    """Check if the model and binary are available."""
    is_model_ok = os.path.exists(MODEL_PATH)
    is_binary_ok = os.path.exists(WHISPER_BINARY_PATH) and os.access(WHISPER_BINARY_PATH, os.X_OK)
    
    logging.info(f"Health check - Model exists: {is_model_ok}, Binary executable: {is_binary_ok}")
    logging.info(f"Model path: {MODEL_PATH}")
    logging.info(f"Binary path: {WHISPER_BINARY_PATH}")
    
    if is_model_ok and is_binary_ok:
        return {"status": "healthy"}
    
    raise HTTPException(
        status_code=503,
        detail={
            "status": "unhealthy",
            "checks": {
                "model_found": is_model_ok,
                "binary_executable": is_binary_ok,
                "model_path": MODEL_PATH,
                "binary_path": WHISPER_BINARY_PATH
            }
        }
    )

@app.post("/transcribe", tags=["Transcription"])
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe an audio or video file.
    The file is first converted to a standard WAV format before processing.
    """
    logging.info(f"Processing file: {file.filename}, content type: {file.content_type}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save uploaded file
        original_filepath = os.path.join(temp_dir, file.filename)
        
        with open(original_filepath, "wb") as f:
            content = await file.read()
            f.write(content)
            logging.info(f"Saved {len(content)} bytes to {original_filepath}")
            
        wav_filepath = os.path.join(temp_dir, "input.wav")

        # Convert audio to WAV format
        try:
            logging.info(f"Converting audio with ffmpeg: {original_filepath} -> {wav_filepath}")
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", original_filepath,
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    wav_filepath
                ],
                check=True, capture_output=True, text=True, timeout=180
            )
            logging.info(f"FFmpeg conversion successful. Output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg conversion failed: {e.stderr}")
            raise HTTPException(status_code=400, detail=f"Audio conversion failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logging.error("FFmpeg conversion timed out.")
            raise HTTPException(status_code=504, detail="Audio conversion timed out.")

        # Check if WAV file was created
        if not os.path.exists(wav_filepath):
            raise HTTPException(status_code=500, detail="WAV file was not created by ffmpeg")

        # Run whisper transcription
        json_output_base = os.path.join(temp_dir, "output")
        
        cmd = [
            WHISPER_BINARY_PATH,
            "-f", wav_filepath,
            "-m", MODEL_PATH,
            "-oj",
            "-of", json_output_base,
            "-t", "4",  # Use 4 threads instead of auto
            "-l", "auto",
        ]

        try:
            logging.info(f"Executing whisper command: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=1200)
            logging.info(f"Whisper transcription successful. Output: {result.stdout}")
            if result.stderr:
                logging.warning(f"Whisper stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Whisper.cpp failed with return code {e.returncode}")
            logging.error(f"Whisper stdout: {e.stdout}")
            logging.error(f"Whisper stderr: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logging.error("Whisper.cpp transcription timed out.")
            raise HTTPException(status_code=504, detail="Transcription timed out.")

        # Read the JSON output
        json_filepath = json_output_base + ".json"
        if not os.path.exists(json_filepath):
            # List files in temp directory for debugging
            files_in_temp = os.listdir(temp_dir)
            logging.error(f"JSON output file not found. Files in temp dir: {files_in_temp}")
            raise HTTPException(status_code=500, detail="Transcription finished but output file was not found.")

        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                result = json.load(f)
                logging.info(f"Successfully loaded JSON result with keys: {result.keys()}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON output: {e}")
            # Try to read the file content for debugging
            with open(json_filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.error(f"JSON file content: {content[:1000]}...")
            raise HTTPException(status_code=500, detail="Failed to parse transcription output")

        # Extract transcription text
        if "transcription" in result and result["transcription"]:
            full_text = " ".join(seg.get("text", "").strip() for seg in result.get("transcription", []))
        else:
            # Alternative: try to get text from different possible structures
            full_text = result.get("text", "")
            if not full_text and "segments" in result:
                full_text = " ".join(seg.get("text", "").strip() for seg in result.get("segments", []))

        return {
            "language": result.get("language", {}).get("language", "unknown") if isinstance(result.get("language"), dict) else result.get("language", "unknown"),
            "full_text": full_text,
            "segments": result.get("transcription", result.get("segments", [])),
            "raw_result": result  # Include raw result for debugging
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
