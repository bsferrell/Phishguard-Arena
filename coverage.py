from collections import Counter

from core.content import load_scenarios
from core.models import WARNING_SIGNS

scenarios = load_scenarios()
phish = [s for s in scenarios if s.is_phishing]
legit = [s for s in scenarios if not s.is_phishing]

print(f"Total: {len(scenarios)}  Phishing: {len(phish)}  Legitimate: {len(legit)}")
print()

print("Difficulty  Phishing  Legitimate")
for level in range(1, 6):
    p = sum(1 for s in phish if s.difficulty == level)
    l = sum(1 for s in legit if s.difficulty == level)
    print(f"    {level}          {p}          {l}")
print()

counts = Counter(sign for s in phish for sign in s.warning_signs)
print("Warning sign coverage (aim for 3 or more each):")
for sign in sorted(WARNING_SIGNS, key=lambda x: counts[x]):
    flag = "  <- needs more" if counts[sign] < 3 else ""
    print(f"  {sign:<24}{counts[sign]}{flag}")