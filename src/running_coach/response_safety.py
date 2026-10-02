import re

UNVERIFIED_SOURCE = re.compile(
    r"\b(?:a study|studies|research|guidelines?|according to|ACSM|American College of Sports Medicine|Journal of [A-Z]|data supports this tip)\b",
    re.IGNORECASE,
)
REFERENCE_SECTION = re.compile(r"(?im)^\s*(?:references|sources|citations)\s*:?\s*$")


def remove_unverified_research(response: str) -> str:
    response = REFERENCE_SECTION.split(response, maxsplit=1)[0]
    paragraphs = re.split(r"\n\s*\n", response)
    kept_paragraphs = []
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        sentences = [sentence for sentence in sentences if not UNVERIFIED_SOURCE.search(sentence)]
        if sentences:
            kept_paragraphs.append(" ".join(sentences))
    return "\n\n".join(kept_paragraphs).strip()
