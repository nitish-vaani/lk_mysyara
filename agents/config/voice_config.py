from dataclasses import dataclass

@dataclass
class VoiceSettings:
    stability: float
    similarity_boost: float
    style: float | None = None
    speed: float | None = 1.0
    use_speaker_boost: bool | None = False

@dataclass
class Voice:
    id: str
    name: str
    category: str
    settings: VoiceSettings | None = None