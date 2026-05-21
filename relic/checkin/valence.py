"""Lightweight heuristic reply valence scoring.

This module provides a small deterministic IT/EN lexicon heuristic. It is not
a trained sentiment model and should be treated as an approximate affect signal.
"""

from __future__ import annotations

import re

_STRONG_POSITIVE_WORDS = frozenset({
    "admirable", "adorato", "adoro", "amazing", "amo", "awesome",
    "bella", "belle", "belli", "bello", "benissimo", "best", "brava", "brave",
    "bravi", "bravo", "calm", "calma", "calme", "calmi", "calmo", "cheerful",
    "comoda", "comode", "comodi", "comodo", "contenta", "contente", "contenti",
    "contentissimo", "contentissima", "contento", "delight", "delighted",
    "divertente", "dolce", "enjoy", "enjoyed", "evviva", "excellent",
    "excited", "fantastic", "fantastico", "fantastica", "felice", "felici",
    "felicissimo", "felicissima", "fortissimo", "gentile", "good", "great",
    "grazie", "grateful", "gratitude", "happy", "interesting", "interessante",
    "joy", "joyful", "kind", "leggera", "leggere", "leggeri", "leggero", "like",
    "liked", "love", "lovely", "loved", "meravigliosa", "meravigliose",
    "meravigliosi", "meraviglioso", "nice", "peaceful", "perfect", "perfetta",
    "perfette", "perfetti", "perfetto", "piace", "piacere", "piaciuta",
    "piaciute", "piaciuti", "piaciuto", "positivo", "positiva", "positive",
    "positivi", "proud", "relax", "relaxed", "relief", "relieved", "serena",
    "serene", "sereni", "sereno", "simpatica", "simpatiche", "simpatici",
    "simpatico", "smile", "splendida", "splendide", "splendidi", "splendido",
    "super", "sweet", "thanks", "thankful", "top", "tranquilla", "tranquille",
    "tranquilli", "tranquillo", "wonderful", "wow",
})

_WEAK_POSITIVE_WORDS = {
    "alright": 0.3,
    "bene": 0.35,
    "better": 0.45,
    "fine": 0.3,
    "meglio": 0.45,
    "ok": 0.25,
    "okay": 0.25,
    "well": 0.3,
}

_NEGATIVE_WORDS = frozenset({
    "angry", "annoying", "ansia", "ansiosa", "ansiose", "ansiosi", "ansioso",
    "anxious", "arrabbiata", "arrabbiate", "arrabbiati", "arrabbiato", "awful",
    "bad", "basta", "boring", "brutta", "brutte", "brutti", "brutto", "confused",
    "delusa", "deluse", "delusi", "delusione", "deluso", "depressed",
    "difficile", "difficili", "fastidio", "fastidiosa", "fastidiose",
    "fastidiosi", "fastidioso", "frustrata", "frustrate", "frustrati",
    "frustrato", "frustrated", "hate", "horrible", "male", "miserable", "negativa",
    "negative", "negativo", "noia", "noiosa", "noiose", "noiosi", "noioso",
    "nervosa", "nervose", "nervosi", "nervoso", "odia", "odiato", "odio",
    "odiosa", "odiose", "odiosi", "odioso", "orribile", "orribili", "paura",
    "peggio", "peggiore", "peggiori", "pessima", "pessime", "pessimi", "pessimo",
    "sad", "scared", "sbagliata", "sbagliate", "sbagliati", "sbagliato", "smettila",
    "solo", "sola", "soli", "solitudine", "stanca", "stanche", "stanchi",
    "stanco", "stressed", "stressata", "stressate", "stressati", "stressato",
    "stufo", "stufa", "stufi", "stufe", "terribile", "terribili", "tired",
    "triste", "tristezza", "tristi", "upset", "useless", "inutile", "worried",
    "worse",
})

_NEGATIONS = frozenset({
    "can't", "cannot", "mai", "mica", "never", "no", "non", "not", "n't",
    "nessun", "nessuna", "nessuno", "never", "neanche",
})

_POSITIVE_EMOJIS = ("🙂", "😊", "😀", "😁", "😄", "😍", "🥰", "😌", "👍", "❤", "❤️")
_NEGATIVE_EMOJIS = ("🙁", "☹", "☹️", "😕", "😞", "😢", "😭", "😠", "😡", "👎")
_PUNCTUATION = frozenset({".", "!", "?", ",", ";", ":"})
_NEGATION_WINDOW = 3
_WORD_RE = r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?"
_EMOJI_RE = "|".join(sorted(
    {re.escape(emoji) for emoji in (*_POSITIVE_EMOJIS, *_NEGATIVE_EMOJIS)},
    key=len,
    reverse=True,
))
_TOKEN_RE = re.compile(rf"{_WORD_RE}|{_EMOJI_RE}|[.!?,;:]", re.UNICODE)


def score_valence(text: str) -> float:
    """Return a deterministic heuristic valence score in [-1.0, 1.0]."""
    if not text:
        return 0.0

    negation_scope = 0
    sentiment_hits = 0
    sentiment_total = 0.0

    for raw_token in _TOKEN_RE.findall(text.lower()):
        token = raw_token.replace("’", "'")

        if token in _PUNCTUATION:
            negation_scope = 0
            continue

        if _is_negation(token):
            negation_scope = _NEGATION_WINDOW
            continue

        token_score = _token_score(token)
        if token_score != 0.0:
            if negation_scope > 0:
                token_score *= -1.0
            sentiment_total += token_score
            sentiment_hits += 1

        if negation_scope > 0:
            negation_scope -= 1

    if sentiment_hits == 0:
        return 0.0

    return _clamp(sentiment_total / sentiment_hits)


def _is_negation(token: str) -> bool:
    return token in _NEGATIONS or token.endswith("n't")


def _token_score(token: str) -> float:
    if token in _WEAK_POSITIVE_WORDS:
        return _WEAK_POSITIVE_WORDS[token]
    if token in _STRONG_POSITIVE_WORDS or token in _POSITIVE_EMOJIS:
        return 1.0
    if token in _NEGATIVE_WORDS or token in _NEGATIVE_EMOJIS:
        return -1.0
    return 0.0


def _clamp(value: float) -> float:
    if value < -1.0:
        return -1.0
    if value > 1.0:
        return 1.0
    return value
