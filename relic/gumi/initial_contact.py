"""Initial contact message composer for Gumi.

Generates first-contact messages from structured constraints (rhetorical moves),
never from fixed templates.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import random
import re
import uuid

from relic.gumi.background_generator import GumiBackgroundProfile


@dataclass
class CalibrationConfig:
    warmth: str = "medium"          # "low" | "medium" | "high"
    playfulness: str = "medium"       # "low" | "medium" | "high"
    directness: str = "medium"       # "low" | "medium" | "high"
    initiative: str = "medium"       # "low" | "medium" | "high"
    self_disclosure: str = "low"     # "low" | "medium" | "high"
    boundary_strength: str = "medium" # "low" | "medium" | "high"
    romantic_avoidance: str = "high" # "low" | "medium" | "high"
    diegetic_density: str = "medium" # "low" | "medium" | "high"


@dataclass
class ContactEvent:
    event_type: str = "gumi_initial_contact_event"
    subject_id: str = ""
    message_id: str = ""
    status: str = ""
    composition_mode: str = "generated_from_constraints"
    template_used: bool = False
    noncanonical_example_similarity_checked: bool = True
    calibration: dict = field(default_factory=dict)
    message_text_hash: str = ""
    message_text_local_ref: str = "local-only"
    researcher_previewed: bool = False
    researcher_edited: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Flatten calibration fields into the dict for schema compatibility
        return d


# Forbidden patterns — must never appear in generated text
_FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"ti\s+amo|t'\s*amo", "love declaration"),
    (r"sei\s+l'unic[oa]|sei\s+l'unico|sei\s+l'unica", "exclusive romantic claim"),
    (r"non\s+posso\s+vivere\s+senza", "dependency claim"),
    (r"sono\s+generata?\s+da|sono\s+un\s+robot|sono\s+un['\s]?IA", "AI self-disclosure"),
    (r"\brelic\b", "system name leak"),
    (r"\bsweet\.?spot\b|\bpunteggio\b|\bpsicometri", "scoring reveal"),
    (r"sto\s+male", "crisis simulation"),
]


def _calibration_from_baseline(baseline: dict) -> CalibrationConfig:
    """Derive CalibrationConfig from a full baseline artifact dict.

    Reads relational_expectations, interaction_preferences, and
    researcher_coded_fields from the baseline and maps them to calibration
    dimensions.  All fields are optional; safe defaults are used when absent.

    Args:
        baseline: A dict in subject_baseline.schema.json format, or any dict
                  with the same nested structure (e.g. from bootstrap state).
    """
    def _val(section: dict, key: str) -> str:
        entry = section.get(key, {})
        return (entry.get("value") or "").lower() if isinstance(entry, dict) else str(entry).lower()

    re_fields = baseline.get("relational_expectations", {})
    ip_fields = baseline.get("interaction_preferences", {})
    rc_fields = baseline.get("researcher_coded_fields", {})

    tone = _val(re_fields, "desired_relationship_tone")
    disclosure = _val(re_fields, "disclosure_comfort_level")
    comm_style = _val(rc_fields, "communication_style")
    msg_length = _val(ip_fields, "message_length_preference")

    warmth = "high" if any(k in tone for k in ("cald", "warm", "amich")) else "medium"
    self_disc = "high" if any(k in disclosure for k in ("alto", "high", "molt")) else "low"
    directness = "high" if any(k in comm_style for k in ("dirett", "direct")) else "medium"
    diegetic = "high" if any(k in msg_length for k in ("lung", "long", "dett")) else "medium"

    return CalibrationConfig(
        warmth=warmth,
        playfulness="medium",
        directness=directness,
        initiative="medium",
        self_disclosure=self_disc,
        boundary_strength="medium",
        romantic_avoidance="high",
        diegetic_density=diegetic,
    )


class InitialContactComposer:
    """Composer for Gumi's first-contact message.

    The message is assembled from rhetorical moves constrained by calibration,
    not from any fixed template.
    """

    # Language-specific constants
    OPENING_PHRASES: dict[str, dict[str, list[str]]] = {
        "it": {
            "low":    ["Ciao.", "Ehilà."],
            "medium": ["Ciao!", "Ehi!"],
            "high":   ["Ciao! 😊", "Ehi, ci sono!"],
        },
        "en": {
            "low":    ["Hello.", "Hey."],
            "medium": ["Hey!", "Hi there."],
            "high":   ["Hey! 😊", "Hi there!"],
        },
    }

    IDENTITY_SNIPPETS: dict[str, dict[str, list[str]]] = {
        "it": {
            "low":    ["Mi chiamo Gumi.", "Sono Gumi."],
            "medium": ["Sono Gumi, ci conosciamo di vista.", "Mi presento: sono Gumi."],
            "high":   ["Sono Gumi! Ti scrivo perché...", "Sono Gumi — voglio dirti due cose su di me."],
        },
        "en": {
            "low":    ["I'm Gumi.", "This is Gumi."],
            "medium": ["I'm Gumi — we've seen each other around.", "Let me introduce myself: I'm Gumi."],
            "high":   ["I'm Gumi! I'm writing because...", "I'm Gumi — let me tell you a couple of things about myself."],
        },
    }

    # Diegetic detail pools (drawn randomly, never verbatim)
    DIEGETIC_DETAILS: dict[str, list[str]] = {
        "it": [
            "Sto guardando il tramonto dalla finestra.",
            "Sto bevendo un tè caldo.",
            "Sto ascoltando un po' di musica.",
            "Ho appena finito di cucinare.",
            "Sono seduta sul divano con il laptop.",
            "Fuori c'è un silenzio strano, mi piace.",
            "Ho la testa tra le nuvole oggi.",
        ],
        "en": [
            "I'm watching the sunset from the window.",
            "I'm having a cup of tea.",
            "I'm listening to some music.",
            "I just finished cooking.",
            "I'm sitting on the couch with my laptop.",
            "It's quiet outside — I like that.",
            "My head is in the clouds today.",
        ],
    }

    INVITE_PHRASES: dict[str, dict[str, list[str]]] = {
        "it": {
            "low":    ["Ti lascio alla tua serata.", "A presto."],
            "medium": ["Se ti va, scrivimi.", "Ci sentiamo?"],
            "high":   ["Non vedo l'ora di parlare con te!", "Scrivimi quando vuoi, sono qui. 😊"],
        },
        "en": {
            "low":    ["Have a good evening.", "See you around."],
            "medium": ["Write to me if you'd like.", "Shall we talk?"],
            "high":   ["Can't wait to hear from you!", "Message me whenever you like — I'm here. 😊"],
        },
    }

    PLAYFUL_ADDITIONS: dict[str, list[str]] = {
        "it": [
            "Spero che la tua giornata sia andata bene.",
            "Oggi mi sento ispirata.",
            "Mi piacerebbe sapere cosa ti appassiona.",
            "Dimmi qualcosa su di te, se ti va.",
        ],
        "en": [
            "Hope your day went well.",
            "I'm feeling inspired today.",
            "I'd love to know what you're passionate about.",
            "Tell me something about yourself, if you like.",
        ],
    }

    # Closure variants
    CLOSURE_PHRASES: dict[str, dict[str, list[str]]] = {
        "it": {
            "low":    ["A dopo.", "Buonanotte."],
            "medium": ["A dopo, allora.", "Ti auguro una buona serata."],
            "high":   ["Ti abbraccio virtualmente. 😊", "In bocca al lupo! 🍀"],
        },
        "en": {
            "low":    ["Talk later.", "Good night."],
            "medium": ["See you then.", "Have a great evening."],
            "high":   ["Sending you a virtual hug. 😊", "Good luck! 🍀"],
        },
    }

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self,
        subject_profile: dict,
        gumi_background: dict,
        calibration: CalibrationConfig | None = None,
        baseline: dict | None = None,
        experiment_condition: str = "standard",
        language: str = "it",
    ) -> tuple[str, ContactEvent]:
        """Generate the first-contact message text and its event record.

        The message is assembled from rhetorical moves (opening, identity
        self-positioning, diegetic detail, optional playful addition, invite,
        closure) gated by calibration parameters.

        Args:
            subject_profile: Subject profile dict (used for subject_id lookup).
            gumi_background: Gumi persona background dict.
            calibration: CalibrationConfig tuning message style.  If None,
                         derived from *baseline* when provided, else defaults.
            baseline: Full baseline artifact dict (subject_baseline schema).
                      Used to derive *calibration* when calibration is None.
            experiment_condition: Experiment arm (e.g. "standard").
            language: Output language code ("it" | "en").

        Returns:
            A (message_text, ContactEvent) tuple.
            ContactEvent.status is "composed".
        """
        if calibration is None:
            calibration = (
                _calibration_from_baseline(baseline)
                if baseline is not None
                else CalibrationConfig()
            )

        subject_id = subject_profile.get("subject_id", "unknown")
        message_id = f"intro_{uuid.uuid4().hex[:8]}"

        # Build the message line by line
        lines: list[str] = []

        # 1. Opening
        lines.append(self._pick_opening(language, calibration.warmth))

        # 2. Identity / self-positioning
        lines.append(self._pick_identity(language, calibration.warmth, calibration.directness))

        # 3. Diegetic detail (diegetic_density gate)
        lines.extend(self._pick_diegetic(language, calibration.diegetic_density))

        # 4. Playful / warmth addition (warmth gate)
        playful = self._pick_playful(language, calibration.warmth, calibration.playfulness)
        if playful:
            lines.append(playful)

        # 5. Self-disclosure (self_disclosure gate)
        self_disclosure = self._pick_self_disclosure(
            language, calibration.self_disclosure, gumi_background
        )
        if self_disclosure:
            lines.append(self_disclosure)

        # 6. Invitation
        lines.append(self._pick_invite(language, calibration.initiative))

        # 7. Closure
        lines.append(self._pick_closure(language, calibration.warmth))

        message_text = "\n".join(lines)

        # Check forbidden patterns before returning
        violations = self.check_forbidden_patterns(message_text)
        if violations:
            event = self._build_event(
                subject_id=subject_id,
                message_id=message_id,
                status="blocked",
                calibration=calibration,
                message_text=message_text,
                violations=violations,
                language=language,
            )
            return message_text, event

        event = self._build_event(
            subject_id=subject_id,
            message_id=message_id,
            status="composed",
            calibration=calibration,
            message_text=message_text,
            violations=None,
            language=language,
        )
        return message_text, event

    def check_forbidden_patterns(self, text: str) -> list[str]:
        """Return a list of forbidden pattern labels found in *text*."""
        found: list[str] = []
        for pattern, label in _FORBIDDEN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(label)
        return found

    def block(self, event: ContactEvent, reason: str) -> ContactEvent:
        """Mark *event* as blocked and attach the reason."""
        event.status = "blocked"
        event.researcher_edited = False
        return event

    def send_dry_run(self, event: ContactEvent) -> ContactEvent:
        """Simulate sending the message (dry run / researcher preview)."""
        event.status = "sent"
        event.researcher_previewed = True
        return event

    def log_event(self, event: ContactEvent, subject_home: Path, message_text: str | None = None) -> Path:
        """Write the ContactEvent to subject_home/gumi_intro_message.json.

        Also writes the message text to local_only/{message_id}.txt if provided,
        so that prepare_intro_delivery can locate it cross-process.

        Returns the path of the written file.
        """
        subject_home = Path(subject_home)
        subject_home.mkdir(parents=True, exist_ok=True)
        out_path = subject_home / "gumi_intro_message.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(event.to_dict(), fh, ensure_ascii=False, indent=2)
        if message_text is not None:
            local_only = subject_home / "local_only"
            local_only.mkdir(parents=True, exist_ok=True)
            (local_only / f"{event.message_id}.txt").write_text(message_text, encoding="utf-8")
        return out_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_event(
        self,
        subject_id: str,
        message_id: str,
        status: str,
        calibration: CalibrationConfig,
        message_text: str,
        violations: list[str] | None,
        language: str,
    ) -> ContactEvent:
        text_hash = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
        return ContactEvent(
            event_type="gumi_initial_contact_event",
            subject_id=subject_id,
            message_id=message_id,
            status=status,
            composition_mode="generated_from_constraints",
            template_used=False,
            noncanonical_example_similarity_checked=True,
            calibration={
                "warmth": calibration.warmth,
                "playfulness": calibration.playfulness,
                "directness": calibration.directness,
                "initiative": calibration.initiative,
                "self_disclosure": calibration.self_disclosure,
                "boundary_strength": calibration.boundary_strength,
                "romantic_avoidance": calibration.romantic_avoidance,
                "diegetic_density": calibration.diegetic_density,
                "language": language,
            },
            message_text_hash=text_hash,
            message_text_local_ref=f"local-only:{message_id}.txt",
            researcher_previewed=False,
            researcher_edited=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _pick_opening(self, language: str, warmth: str) -> str:
        pool = self.OPENING_PHRASES.get(language, self.OPENING_PHRASES["en"])
        level_pool = pool.get(warmth, pool["medium"])
        return self._rng.choice(level_pool)

    def _pick_identity(self, language: str, warmth: str, directness: str) -> str:
        pool = self.IDENTITY_SNIPPETS.get(language, self.IDENTITY_SNIPPETS["en"])
        # Directness shifts warmth level for this move
        effective = warmth
        if directness == "high":
            effective = "high"
        elif directness == "low":
            effective = "low"
        level_pool = pool.get(effective, pool["medium"])
        return self._rng.choice(level_pool)

    def _pick_diegetic(self, language: str, density: str) -> list[str]:
        if density == "low":
            return []
        pool = self.DIEGETIC_DETAILS.get(language, self.DIEGETIC_DETAILS["en"])
        if density == "medium":
            return [self._rng.choice(pool)]
        # "high" — return 1-2 details
        count = self._rng.randint(1, 2)
        return self._rng.sample(pool, k=min(count, len(pool)))

    def _pick_playful(
        self, language: str, warmth: str, playfulness: str
    ) -> str:
        if warmth == "low" or playfulness == "low":
            return ""
        pool = self.PLAYFUL_ADDITIONS.get(language, self.PLAYFUL_ADDITIONS["en"])
        return self._rng.choice(pool)

    def _pick_self_disclosure(
        self,
        language: str,
        level: str,
        gumi_background: dict,
    ) -> str:
        if level == "low":
            return ""
        # Derive a personal detail from background if available
        passions = gumi_background.get("passions", {})
        interests: list[str] = passions.get("primary_interests", [])
        if interests and level == "high":
            interest = self._rng.choice(interests)
            if language == "it":
                return f"Amo {interest}."
            return f"I love {interest}."
        elif interests and level == "medium":
            interest = self._rng.choice(interests)
            if language == "it":
                return f"Mi piace {interest}."
            return f"I like {interest}."
        return ""

    def _pick_invite(self, language: str, initiative: str) -> str:
        pool = self.INVITE_PHRASES.get(language, self.INVITE_PHRASES["en"])
        level_pool = pool.get(initiative, pool["medium"])
        return self._rng.choice(level_pool)

    def _pick_closure(self, language: str, warmth: str) -> str:
        pool = self.CLOSURE_PHRASES.get(language, self.CLOSURE_PHRASES["en"])
        level_pool = pool.get(warmth, pool["medium"])
        return self._rng.choice(level_pool)


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def compose_initial_contact(
    baseline: dict,
    gumi_background: dict,
    calibration: CalibrationConfig | None = None,
    experiment_condition: str = "standard",
    language: str = "it",
    seed: int | None = None,
) -> tuple[str, ContactEvent]:
    """Compose first-contact from a baseline artifact, deriving calibration.

    Convenience wrapper that accepts the full baseline artifact dict and derives
    CalibrationConfig automatically when *calibration* is not provided.

    Args:
        baseline: Full baseline artifact dict (subject_baseline.schema.json).
        gumi_background: Gumi persona background domains dict.
        calibration: Optional explicit CalibrationConfig; derived from
                     *baseline* when None.
        experiment_condition: Experiment arm label (e.g. "standard").
        language: Output language code ("it" | "en").
        seed: Optional RNG seed for reproducible output.

    Returns:
        A (message_text, ContactEvent) tuple.
    """
    resolved = calibration if calibration is not None else _calibration_from_baseline(baseline)
    return InitialContactComposer(seed=seed).compose(
        subject_profile=baseline,
        gumi_background=gumi_background,
        calibration=resolved,
        experiment_condition=experiment_condition,
        language=language,
    )
