WARNING_SIGNS = [
    "Suspicious_URL",
    "Urgent_Request",
    "Sensitive_Information_Request",
    "Unexpected_Request_for_Credentials",
    "Odd_Sender",
    "Lookalike_Domain",
    "Unexpected_Attachment",
    "Unexpected_Redirect",
    "Mismatched_Link",
    "Generic_Greeting",
]

DECOYS_PER_ROUND = 2

from pydantic import BaseModel

class Scenario(BaseModel):
    scenario_id: str
    channel: str # "email", "sms", etc.
    is_phishing: bool
    difficulty: int # 1-5, with 1 being easiest and 5 being hardest
    subject: str
    body: str
    warning_signs: list[str] # List of warning signs present in this scenario
    decoy_signs: list[str] # List of decoy warning signs present in this scenario
    policy_refs: list[str] # List of policy references relevant to this scenario

class KnowledgePassage(BaseModel):
    policy_id: str
    title: str
    tags: list[str] # List of warning signs associated with this knowledge passage
    body: str

