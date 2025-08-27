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

    if is_model_ok and is_binary_ok:
        return {"status": "healthy"}
    
    raise HTTPException(
        status_code=503,
        detail={
            "status": "unhealthy",
            "checks": {
                "model_found": is_model_ok,
                "binary_executable": is_binary_ok
            }
        }
    )

@app.post("/transcribe", tags=["Transcription"])
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe an audio or video file.
    The file is first converted to a standard WAV format before processing.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        original_filepath = os.path.join(temp_dir, file.filename)
        
        with open(original_filepath, "wb") as f:
            f.write(await file.read())
            
        wav_filepath = os.path.join(temp_dir, "input.wav")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", original_filepath,
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    wav_filepath
                ],
                check=True, capture_output=True, text=True, timeout=180
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg conversion failed: {e.stderr}")
            raise HTTPException(status_code=400, detail=f"Audio conversion failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logging.error("FFmpeg conversion timed out.")
            raise HTTPException(status_code=504, detail="Audio conversion timed out.")

        json_output_base = os.path.join(temp_dir, "output")
        
        cmd = [
            WHISPER_BINARY_PATH,
            "-f", wav_filepath,
            "-m", MODEL_PATH,
            "-oj",
            "-of", json_output_base,
            "-t", "auto",
            "-l", "auto",
        ]

        try:
            logging.info(f"Executing whisper command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=1200)
        except subprocess.CalledProcessError as e:
            logging.error(f"Whisper.cpp failed: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logging.error("Whisper.cpp transcription timed out.")
            raise HTTPException(status_code=504, detail="Transcription timed out.")

        json_filepath = json_output_base + ".json"
        if not os.path.exists(json_filepath):
            raise HTTPException(status_code=500, detail="Transcription finished but output file was not found.")

        with open(json_filepath, 'r', encoding='utf-8') as f:
            result = json.load(f)

        full_text = " ".join(seg.get("text", "").strip() for seg in result.get("transcription", []))

        return {
            "language": result.get("language", {}).get("language", "unknown"),
            "full_text": full_text,
            "segments": result.get("transcription", [])
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
