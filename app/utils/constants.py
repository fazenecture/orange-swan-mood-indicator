import re


# ── Post types ────────────────────────────────────────────────────────────────
class PostType:
    ORIGINAL = "original"
    LINK_SHARE = "link_share"
    RETRUTH = "retruth"


# ── Signal strengths ──────────────────────────────────────────────────────────
class SignalStrength:
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Mood labels ───────────────────────────────────────────────────────────────
class MoodLabel:
    COMBATIVE = "COMBATIVE"
    TRIUMPHANT = "TRIUMPHANT"
    GRIEVANCE = "GRIEVANCE"
    RALLYING = "RALLYING"
    AGITATED = "AGITATED"
    TRANSACTIONAL = "TRANSACTIONAL"
    DEFIANT = "DEFIANT"
    CELEBRATORY = "CELEBRATORY"
    UNKNOWN = "UNKNOWN"


# ── Intensity levels ──────────────────────────────────────────────────────────
class Intensity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FRENETIC = "frenetic"


# ── Regex patterns ────────────────────────────────────────────────────────────
NICKNAME_PATTERN = re.compile(
    r"sleepy|crooked|radical|fake news|witch hunt|lamestream|"
    r"deranged|crazy nancy|shifty|do nothing|rhino|rino",
    re.IGNORECASE,
)

SUPERLATIVE_PATTERN = re.compile(
    r"greatest|best ever|nobody does|tremendous|perfect|"
    r"most beautiful|strongest|smartest|most successful",
    re.IGNORECASE,
)

URL_PATTERN = re.compile(r"https?://\S+")

# ── HuggingFace zero-shot candidates ─────────────────────────────────────────
ZEROSHOT_MOOD_CANDIDATES = [
    "combative and attacking opponents",
    "triumphant and celebrating victory",
    "grievance and feeling victimized",
    "rallying supporters with energy",
    "making policy or business announcements",
    "defiant and issuing challenges",
]
