WARNING_SIGNS = [
    "Suspicious URL",
    "Urgent Request",
    "Sensitive Information Request",
    "Unexpected Request for Credentials",
    "Odd Sender",
    "Lookalike Domain",
    "Unexpected Attachment",
    "Unexpected Redirect",
    "Mismatched Link",
    "Generic Greeting",
]

DECOYS_PER_ROUND = 2

from pydantic import BaseModel

class Scenario(BaseModel):
    scenario_id: str
    channel: str # "email", "sms", etc.
    is_phishing: bool
    difficulty: str # 1-5, with 1 being easiest and 5 being hardest
    subject: str
    body: str
    warning_signs: list[str] # List of warning signs present in this scenario
    decoy_signs: list[str] # List of decoy warning signs present in this scenario
    policy_refs: list[str] # List of policy references relevant to this scenario

    