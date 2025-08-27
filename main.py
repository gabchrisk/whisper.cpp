from fastapi import FastAPI, UploadFile
import subprocess

app = FastAPI()

@app.post("/transcribe")
async def transcribe(file: UploadFile):
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    result = subprocess.run(["./build/main", "-f", file_path], capture_output=True, text=True)
    return {"transcription": result.stdout}
