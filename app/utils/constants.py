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


# ── URL pattern ───────────────────────────────────────────────────────────────
URL_PATTERN = re.compile(r"https?://\S+")


# ── Nickname pattern ──────────────────────────────────────────────────────────
# Every label he has ever used for opponents, media, institutions
NICKNAME_PATTERN = re.compile(
    r"sleepy joe|sleepy|crooked hillary|crooked|"
    r"radical left|radical democrat|radical|"
    r"fake news|lamestream media|lamestream|"
    r"witch hunt|hoax|scam|"
    r"deranged|lunatic|"
    r"crazy nancy|cryin chuck|nervous nancy|"
    r"shifty schiff|liddle adam|"
    r"do nothing democrat|"
    r"rhino|rino|"
    r"meatball ron|ron desanctimonious|"
    r"birdbrain|nikki|"
    r"pencil neck|"
    r"pocahontas|"
    r"liddle|little|"
    r"low iq|"
    r"failing new york times|failing nyt|"
    r"amazon washington post|"
    r"corrupt|"
    r"third world|"
    r"enemy of the people|"
    r"swamp|deep state|"
    r"globalist|"
    r"radical left lunatic",
    re.IGNORECASE,
)


# ── Superlative pattern ───────────────────────────────────────────────────────
# Things he says when in triumphant or rallying mode
SUPERLATIVE_PATTERN = re.compile(
    r"greatest|best ever|nobody does it better|"
    r"tremendous|perfect|beautiful|"
    r"strongest|smartest|richest|"
    r"most successful|most popular|"
    r"historic|historically|"
    r"record|record-breaking|all-time|"
    r"unmatched|unparalleled|"
    r"like never before|like nobody has ever|"
    r"incredible|unbelievable|"
    r"massive|huge|gigantic|"
    r"total|complete|absolute|"
    r"winning|winner|"
    r"America first|"
    r"make america great|maga|"
    r"landslide|"
    r"overwhelming",
    re.IGNORECASE,
)


# ── Grievance pattern ─────────────────────────────────────────────────────────
# Language he uses when feeling victimized — a new pattern we weren't tracking
GRIEVANCE_PATTERN = re.compile(
    r"witch hunt|"
    r"hoax|total hoax|"
    r"rigged|stolen|"
    r"unfair|not fair|"
    r"persecuted|persecution|"
    r"weaponized|weaponization|"
    r"two-tiered|two tiered|"
    r"corrupt judge|corrupt court|"
    r"never seen anything like|"
    r"they are after|going after|coming after|"
    r"election interference|"
    r"political prosecution|political prisoner|"
    r"unconstitutional|"
    r"no president has ever|"
    r"presidential harassment|"
    r"should be ashamed|"
    r"disgrace|disgusting|"
    r"lawfare",
    re.IGNORECASE,
)


# ── Aggression pattern ────────────────────────────────────────────────────────
# Direct attack language — distinct from nickname usage
AGGRESSION_PATTERN = re.compile(
    r"destroy|destroyed|"
    r"demolish|"
    r"obliterate|"
    r"kill|killed|"
    r"hammer|"
    r"crush|crushed|"
    r"exposing|exposed|"
    r"beat|beaten|"
    r"slam|slammed|"
    r"rip|ripped|"
    r"sue|suing|lawsuit|"
    r"prosecute|prosecuted|"
    r"lock up|locked up|"
    r"prison|jail|"
    r"traitor|treason|"
    r"investigate|"
    r"subpoena",
    re.IGNORECASE,
)


# ── Rally / call to action pattern ───────────────────────────────────────────
RALLY_PATTERN = re.compile(
    r"maga|"
    r"make america great|"
    r"america first|"
    r"save america|"
    r"fight for|fight back|"
    r"stand up|stand together|"
    r"we will win|we are winning|"
    r"join me|join us|"
    r"vote|get out and vote|"
    r"rally|"
    r"together we|"
    r"our country|take back|"
    r"patriots|"
    r"movement|"
    r"revolution|"
    r"drain the swamp|"
    r"enough is enough|"
    r"now or never",
    re.IGNORECASE,
)


# ── HuggingFace zero-shot candidates ─────────────────────────────────────────
# More specific candidates = more accurate zero-shot classification
ZEROSHOT_MOOD_CANDIDATES = [
    # Attack
    "attacking and insulting political opponents by name",
    "calling for investigations or prosecution of opponents",
    "declaring war on the media and fake news",

    # Grievance
    "expressing victimhood and claiming unfair treatment",
    "complaining about witch hunts and political persecution",
    "expressing outrage at court decisions and legal rulings",

    # Triumphant
    "celebrating personal victory and boasting about achievements",
    "claiming credit for economic success and record numbers",

    # Rallying
    "rallying supporters with patriotic and energetic language",
    "calling on supporters to fight back and take action",

    # Defiant
    "issuing direct threats and defiant challenges to opponents",
    "challenging the legitimacy of institutions and the judiciary",

    # Transactional
    "announcing policy decisions or executive orders",

    # Agitated
    "posting rapid fire reactions to live breaking news",

    # Defensive
    "defending himself against criminal charges and indictments",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]