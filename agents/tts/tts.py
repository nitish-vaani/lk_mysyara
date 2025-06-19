import yaml
from livekit.plugins import (
    aws,
    cartesia,
    deepgram,
    elevenlabs,
    neuphonic,
    openai,
    rag,
    silero,
    google
)

with open("/app/config/engine_config.yml", "r") as file:
    config = yaml.safe_load(file)


def __get_tts():
    which_tts = config["TTS"]
    match which_tts:
        case "aws":
            return aws.TTS(
                voice="Kajal",
                speech_engine="neural",
                language="hi-IN",
            )
        case "elevenlabs":
            from dataclasses import dataclass

            @dataclass
            class VoiceSettings:
                stability: float  # [0.0 - 1.0]
                similarity_boost: float  # [0.0 - 1.0]
                style: float | None = None  # [0.0 - 1.0]
                speed: float | None = 1.0  # [0.8 - 1.2]
                use_speaker_boost: bool | None = False

            @dataclass
            class Voice:
                id: str
                name: str
                category: str
                settings: VoiceSettings | None = None

            male_voice = Voice(
                id="1qZOLVpd1TVic43MSkFY", 
                name="Amritanshu Professional voice",
                category="professional",
                settings=VoiceSettings(
                    stability=0.7,
                    speed=1.0,
                    similarity_boost=0.6,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )
            female_voice = male_voice
            female_voice = Voice(
                id="ZUrEGyu8GFMwnHbvLhv2",
                name="Monika",
                category="professional",
                settings=VoiceSettings(
                    stability=0.8,
                    speed=1.1,
                    similarity_boost=0.4,
                    style=1.0,
                    use_speaker_boost=True,
                ),
            )
            return elevenlabs.TTS(model="eleven_flash_v2_5", voice=female_voice)
        case "cartesia":
            return cartesia.TTS(
                # model="sonic-2",
                model="sonic-2-2025-03-07",
                voice="28ca2041-5dda-42df-8123-f58ea9c3da00",  # "bec003e2-3cb3-429c-8468-206a393c67ad",#Parvati #fast speaking female:"faf0731e-dfb9-4cfc-8119-259a79b27e12", #male:"d088cdf6-0ef0-4656-aea8-eb9b004e82eb",
                speed=0,
                language="hi",
                emotion=["positivity:highest", "curiosity:highest"],
            )
        case "neuphonic":
            return neuphonic.TTS(
                voice_id="e7492a4d-f096-4903-a89c-0c00aad35023", lang_code="hi"
            )
        case "azure":
            raise ValueError(
                "Currently Azure is not supported. When adding this, Bhudev found that azure api authentication is failing, might be some bug in livekit-plugins-azure lib. Need to RCA/Fix."
            )
            # return azure.TTS(
            #     speech_key="GCqxGkmzxtXuahHkJEcCrtQrp2Ls2Sb3YC1FknolAS6rkE1pStDcJQQJ99BDACGhslBXJ3w3AAAYACOGZkCd",
            #     speech_region="cetralindia",
            #     voice="hi-IN-AaravNeural",
            #     speech_host=None
            #     # speech_host="https://centralindia.api.cognitive.microsoft.com/"
            # )
        case "playai":
            raise ValueError(
                "Currently playai is not supported. When adding this, Bhudev found that playai does not give enough free credits to try their tts models. If you need playai tts, buy their subscription and integrate =D"
            )
            # return playai.TTS(
            #     voice="s3://voice-cloning-zero-shot/6f3decaf-f64f-414a-b16a-f8a1492d28a6/original/manifest.json",
            #     language="hindi",
            #     model="play3.0-mini"
            # )
