from fastapi import FastAPI, UploadFile, File, HTTPException
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
    # Validasi tipe file
    allowed_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4', '.avi', '.mov']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Membuat file temporer dengan suffix yang sesuai
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file_path = temp_file.name
        content = await file.read()
        temp_file.write(content)
    
    json_file_path = temp_file_path + ".json"

    try:
        # Path absolut ke binary dan model di dalam kontainer
        whisper_binary = "/app/whisper.cpp/build/main"
        model_path = "/app/models/ggml-small.bin"
        
        # Cek keberadaan file sebelum eksekusi
        if not os.path.exists(whisper_binary):
            raise HTTPException(status_code=500, detail="Whisper binary not found at " + whisper_binary)
        if not os.path.exists(model_path):
            raise HTTPException(status_code=500, detail="Whisper model not found at " + model_path)
        
        # Perintah untuk menjalankan whisper.cpp
        cmd = [
            whisper_binary,
            "-f", temp_file_path,
            "-m", model_path,
            "-oj",  # Output format JSON (ke file)
            "-t", "4",  # Jumlah threads
            "--language", "auto"  # Deteksi bahasa otomatis
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # Timeout 5 menit
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, 
                detail=f"Whisper processing failed: {result.stderr}"
            )
        
        # Dengan flag -oj, output ada di file JSON, bukan stdout.
        # Cek apakah file JSON output benar-benar dibuat.
        if not os.path.exists(json_file_path):
            raise HTTPException(
                status_code=500,
                detail=f"Whisper process succeeded but output JSON file not found. Stderr: {result.stderr}"
            )

        # Baca dan parse file JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_output = json.load(f)
        
        # Gabungkan semua segmen teks menjadi satu string
        full_text = " ".join([
            segment.get("text", "") for segment in json_output.get("transcription", [])
        ]).strip()

        # Ekstrak bahasa yang terdeteksi dengan lebih aman
        detected_language = json_output.get("language", {}).get("language", "unknown")

        return {
            "success": True,
            "transcription": json_output.get("transcription", []),
            "text": full_text,
            "language": detected_language,
            "model": "ggml-small.bin",
            "filename": file.filename
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Transcription process timed out after 5 minutes.")
    except Exception as e:
        # Tangkap semua error lain dan berikan detail
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # Selalu pastikan file temporer dihapus
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(json_file_path):
            os.remove(json_file_path)
