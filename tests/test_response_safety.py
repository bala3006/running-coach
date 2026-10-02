from running_coach.response_safety import remove_unverified_research


def test_removes_unverified_studies_and_reference_sections() -> None:
    response = (
        "Try gentle movement and rest if you feel tired. "
        "A study published in a journal proves this works.\n\n"
        "References:\n1. An invented journal article (2025)"
    )

    assert remove_unverified_research(response) == "Try gentle movement and rest if you feel tired."


def test_keeps_general_advice_without_claimed_sources() -> None:
    assert remove_unverified_research("Take an easy day if your legs feel heavy.") == (
        "Take an easy day if your legs feel heavy."
    )