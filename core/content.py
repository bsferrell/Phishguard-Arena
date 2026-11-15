import json
from pathlib import Path

from models import (
    DECOYS_PER_ROUND, WARNING_SIGNS, KnowledgePassage, Scenario,
)

DATA = Path(__file__).resolve().parent.parent / "data"


def load_passages():
    raw = json.loads((DATA / "knowledge" / "passages.json").read_text())
    return [KnowledgePassage(**p) for p in raw]


def load_scenarios():
    raw = json.loads((DATA / "scenarios.json").read_text())
    return [Scenario(**s) for s in raw]


def check():
    errors = []
    passages = load_passages()
    policy_ids = {p.policy_id for p in passages}
    for p in passages:
        bad = set(p.tags) - set(WARNING_SIGNS)
        if bad:
            errors.append(f"{p.policy_id}: unknown tags {bad}")

    scenarios = load_scenarios()
    seen = set()
    for s in scenarios:
        sid = s.scenario_id
        if sid in seen:
            errors.append(f"{sid}: duplicate ID")
        seen.add(sid)
        if not 1 <= s.difficulty <= 5:
            errors.append(f"{sid}: difficulty out of range")
        if s.channel not in ("email", "sms"):
            errors.append(f"{sid}: bad channel")
        for name in s.warning_signs + s.decoy_signs:
            if name not in WARNING_SIGNS:
                errors.append(f"{sid}: unknown sign {name}")
        if set(s.warning_signs) & set(s.decoy_signs):
            errors.append(f"{sid}: decoy overlaps a real sign")
        if len(s.decoy_signs) != DECOYS_PER_ROUND:
            errors.append(f"{sid}: needs exactly {DECOYS_PER_ROUND} decoys")
        if s.is_phishing and not s.warning_signs:
            errors.append(f"{sid}: phishing with no warning signs")
        if not s.is_phishing and s.warning_signs:
            errors.append(f"{sid}: legitimate but has warning signs")
        for ref in s.policy_refs:
            if ref not in policy_ids:
                errors.append(f"{sid}: policy {ref} does not exist")

    phish = sum(s.is_phishing for s in scenarios)
    print(f"{len(scenarios)} scenarios ({phish} phishing), "
          f"{len(passages)} passages")
    for e in errors:
        print("ERROR", e)
    print("All checks passed" if not errors else f"{len(errors)} errors")


if __name__ == "__main__":
    check()