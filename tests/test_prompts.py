import pytest

from running_coach.prompts import build_system_prompt


@pytest.mark.parametrize("language", ["en", "en-ta", "ta", "tanglish"])
def test_prompt_preserves_requested_language(language: str) -> None:
    assert build_system_prompt(language, tamil_voice=False)


def test_english_tamil_mode_uses_friendly_natural_tanglish() -> None:
    prompt = build_system_prompt("en-ta", tamil_voice=True)

    assert "clear, warm English" in prompt
    assert "light, natural Tanglish" in prompt
    assert "Romanized Tamil" in prompt
    assert "Do not force catchphrases" in prompt
    assert "vetted phrase" not in prompt
    assert "Do not invent studies, citations, organizations, or guidelines" in prompt


def test_tamil_voice_is_respectful_and_localized() -> None:
    prompt = build_system_prompt("ta", tamil_voice=True)

    assert "Tamil-speaking running coach" in prompt
    assert "stereotypes" in prompt
    assert "diagnose injuries" in prompt


def test_unsupported_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported coach language"):
        build_system_prompt("fr", tamil_voice=False)
