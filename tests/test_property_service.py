from src.property_service import decide_priority


def test_hazard_in_transcript_becomes_urgent() -> None:
    transcript = "The tenant reports a gas leak beside the kitchen meter."

    assert decide_priority(transcript) == "urgent"


def test_normal_repair_stays_routine() -> None:
    assert decide_priority("The hallway light is out.") == "routine"
