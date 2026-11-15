from core.mastery import START, next_level, update_mastery
from core.scoring import Response, score
from tests.test_scoring import PHISH


def test_found_sign_rises_missed_sign_falls():
    result = score(PHISH, Response(verdict_phishing=True, confidence=3,
                                   selected=["lookalike_domain"]))
    m = update_mastery({}, PHISH, result)
    assert m["lookalike_domain"] > START
    assert m["urgent_pressure"] < START


def test_decoy_lowers_that_sign():
    result = score(PHISH, Response(verdict_phishing=True, confidence=3,
                                   selected=["lookalike_domain",
                                             "urgent_pressure",
                                             "generic_greeting"]))
    m = update_mastery({}, PHISH, result)
    assert m["generic_greeting"] < START


def test_moves_thirty_percent():
    result = score(PHISH, Response(verdict_phishing=True, confidence=3,
                                   selected=["lookalike_domain",
                                             "urgent_pressure"]))
    m = update_mastery({"lookalike_domain": 0.0}, PHISH, result)
    assert m["lookalike_domain"] == 0.3


def test_level_rules():
    assert next_level(2, [True] * 4) == 2                 # not enough rounds
    assert next_level(2, [True, True, True, True, False]) == 3
    assert next_level(2, [True, True, False, False, False]) == 1
    assert next_level(2, [True, True, True, False, False]) == 2
    assert next_level(5, [True] * 5) == 5                 # capped at top
    assert next_level(1, [False] * 5) == 1                # capped at bottom