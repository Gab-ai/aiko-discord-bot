# tts.py
import edge_tts
import uuid
import os

async def text_to_speech(text, voice="en-US-JennyNeural"):
    filename = f"tts_{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)
    return filename

def cleanup_audio_file(filename):
    if os.path.exists(filename):
        os.remove(filename)
