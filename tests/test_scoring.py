from core.models import Scenario
from core.scoring import Response, score

PHISH = Scenario(
    scenario_id="T-PHISH", channel="email", is_phishing=True, difficulty=2,
    subject="Password expires today", body="From: it@carolinaridgehea1th.org",
    warning_signs=["lookalike_domain", "urgent_pressure"],
    decoy_signs=["generic_greeting", "unexpected_attachment"],
    policy_refs=["POLICY-DOMAIN02", "POLICY-URG01", "POLICY-REP01"],
)

LEGIT = Scenario(
    scenario_id="T-LEGIT", channel="email", is_phishing=False, difficulty=1,
    subject="Staff meeting moved", body="From: hr@carolinaridgehealth.org",
    warning_signs=[],
    decoy_signs=["urgent_pressure", "odd_sender"],
    policy_refs=[],
)


def test_correct_with_all_signs():
    r = score(PHISH, Response(verdict_phishing=True, confidence=4,
                              selected=["lookalike_domain", "urgent_pressure"]))
    assert r.correct and r.points == 10
    assert r.missed == [] and r.false_hits == []
    assert not r.has_errors


def test_correct_but_decoy_picked():
    r = score(PHISH, Response(verdict_phishing=True, confidence=4,
                              selected=["lookalike_domain", "urgent_pressure",
                                        "generic_greeting"]))
    assert r.correct
    assert r.false_hits == ["generic_greeting"]
    assert r.points == 8
    assert r.has_errors


def test_wrong_while_confident():
    r = score(PHISH, Response(verdict_phishing=False, confidence=5,
                              selected=[]))
    assert not r.correct
    assert r.points == -10
    assert r.missed == ["lookalike_domain", "urgent_pressure"]


def test_wrong_while_unsure():
    r = score(PHISH, Response(verdict_phishing=False, confidence=1,
                              selected=[]))
    assert not r.correct
    assert r.points == -2


def test_legitimate_correctly_passed():
    r = score(LEGIT, Response(verdict_phishing=False, confidence=3,
                              selected=[]))
    assert r.correct and r.points == 10
    assert not r.has_errors