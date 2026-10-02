from running_coach.voice import PHRASES, add_english_tamil_touch


def test_english_tamil_mode_replaces_model_generated_tamil() -> None:
    model_response = (
        "Take an easy day after a good run. In the meantime, a little Tamil phrase "
        "to keep you motivated: 'நேரம் இருக்கும், செயலூட்டும்' - 'Time is ripe, let's take action!'"
    )

    response = add_english_tamil_touch(model_response)

    assert "நேரம் இருக்கும்" not in response
    assert "Time is ripe" not in response
    assert "a little Tamil phrase" not in response
    assert response.endswith(PHRASES["rest"])


def test_safety_context_selects_body_awareness_phrase() -> None:
    assert add_english_tamil_touch("Stop running if you have sharp pain.").endswith(
        PHRASES["body"]
    )


def test_sanitizer_removes_empty_parentheses() -> None:
    assert "()" not in add_english_tamil_touch("Good work (நல்லது).")


def test_sanitizer_removes_camel_case_tamil_transliteration() -> None:
    model_response = "Good recovery. (IravuKaal Unarthurtha MeeNdum KaVanaM Selutthungal)"

    response = add_english_tamil_touch(model_response)

    assert "IravuKaal" not in response
    assert "MeeNdum" not in response
    assert "()" not in response