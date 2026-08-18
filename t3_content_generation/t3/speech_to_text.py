import json
from pathlib import Path

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


# https://developers.openai.com/api/docs/guides/speech-to-text

#TODO:
# You need to transcribe 'audio_sample.mp3':
#   - Create Client that will go to transcriptions OpenAI API
#   - Call API and provide file (pay attention that you work with 'multipart/form-data')
#   - Get response with transcription
# ---
# Hints:
#   - Use /v1/audio/transcriptions endpoint
#   - Use whisper-1 or gpt-4o-transcribe model

audio_path = Path(__file__).parent / "audio_sample.mp3"

for model in ("whisper-1", "gpt-4o-transcribe"):
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            url=f"{OPENAI_HOST}/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": audio_file},
            data={"model": model}
        )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    print(f"--- {model} ---")
    print(json.dumps(response.json(), indent=2))