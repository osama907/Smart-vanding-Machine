from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os

from voice_module import speech_to_text
from functional_calling_database import handle_conversation
from vision import person_des


app = FastAPI()

@app.post("/voice-chat/")
async def voice_chat(audio: UploadFile = File(...)):
    # Validate file type (optional)
    if not audio.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only .wav files are accepted.")

    # Save uploaded audio to a temporary file
    temp_file_path = f"temp_{audio.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)

    try:
        # Step 1: Transcribe audio to text
        transcript = speech_to_text(temp_file_path)
        
        # Step 2: Send transcribed text to conversation handler
        ai_response = handle_conversation(transcript)

    finally:
        # Clean up temp file
        os.remove(temp_file_path)

    # Return AI response text as JSON
    return {
        "transcript": transcript,
        "response": ai_response
    }


@app.post("/image-chat/")
async def image_chat(image: UploadFile = File(...)):
    if not image.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400, detail="Only jpg/jpeg/png images accepted.")

    image_bytes = await image.read()

    description = person_des(image_bytes, filename=image.filename)

    response_text = handle_conversation(description)

    return {
        "description": description,
        "response": response_text
    }