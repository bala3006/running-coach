import re

TAMIL_SCRIPT = re.compile(r"[\u0B80-\u0BFF]+(?:[\s,!?;:.]+[\u0B80-\u0BFF]+)*[.!?]?")
TAMIL_ASIDE = re.compile(
    r"\b(?:in the meantime,?\s+)?(?:(?:a|one)\s+)?(?:little\s+)?tamil phrase\b[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)
PARENTHETICAL = re.compile(r"\(([^()\n]{1,120})\)")
PHRASES = {
    "rest": "இன்று ஓய்வும் பயிற்சியின் ஒரு பகுதி.",
    "body": "உடம்பு சொல்வதைக் கேளுங்கள்.",
    "progress": "அருமை, நல்ல முன்னேற்றம்.",
    "steady": "சரி, நிதானமா போகலாம்.",
}


def add_english_tamil_touch(response: str) -> str:
    cleaned = TAMIL_ASIDE.sub("", response)
    cleaned = TAMIL_SCRIPT.sub("", cleaned)
    cleaned = PARENTHETICAL.sub(
        lambda match: "" if _looks_like_transliteration(match.group(1)) else match.group(0),
        cleaned,
    )
    cleaned = re.sub(r"[\"'“”‘’]+", "", cleaned)
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", "", cleaned)
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    lowered = cleaned.lower()
    if any(word in lowered for word in ("injury", "pain", "symptom", "stop running")):
        phrase = PHRASES["body"]
    elif any(word in lowered for word in ("rest", "recovery", "recover", "sleep", "easy day", "easy run")):
        phrase = PHRASES["rest"]
    elif any(word in lowered for word in ("great", "well done", "good progress", "nice work")):
        phrase = PHRASES["progress"]
    else:
        phrase = PHRASES["steady"]
    return f"{cleaned}\n\n{phrase}" if cleaned else phrase


def _looks_like_transliteration(value: str) -> bool:
    words = re.findall(r"[A-Za-z]+", value)
    internal_capitals = sum(any(char.isupper() for char in word[1:]) for word in words)
    return len(words) >= 3 and internal_capitals >= 2
