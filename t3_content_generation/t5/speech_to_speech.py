import base64
import json
from datetime import datetime
from pathlib import Path

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


# https://developers.openai.com/api/docs/guides/audio#add-audio-to-your-existing-application

#TODO:
# You need to generate answer in audio format based on the audio message:
#   - Create Client that is similar with OpenAIClients but extracts from message audio (instead of content)
#   - Call API
#   - Get response as base64 content, decode and save as .mp3 file
# ---
# Hints:
#   - Use /v1/chat/completions endpoint
#   - Use gpt-4o-audio-preview model
#   - Use modalities=["text", "audio"]
#   - Use audio={"voice": "ballad", "format": "mp3"}
#   - Use similar method to encode audio as you have done for images encoding

question_path = Path(__file__).parent / "question.mp3"
question_base64 = base64.b64encode(question_path.read_bytes()).decode("utf-8")

response = requests.post(
    url=f"{OPENAI_HOST}/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "gpt-audio-1.5",  # account has no access to gpt-4o-audio-preview (TODO's original model) — using its successor
        "modalities": ["text", "audio"],
        "audio": {"voice": "ballad", "format": "mp3"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": question_base64, "format": "mp3"}}
                ]
            }
        ]
    }
)

if response.status_code != 200:
    raise Exception(f"HTTP {response.status_code}: {response.text}")

data = response.json()
print(json.dumps(data, indent=2))

audio_base64 = data["choices"][0]["message"]["audio"]["data"]
output_path = f"{Path(__file__).parent}/answer_{datetime.now():%Y%m%d_%H%M%S}.mp3"

with open(output_path, "wb") as f:
    f.write(base64.b64decode(audio_base64))

print(f"Audio saved to {output_path}")
