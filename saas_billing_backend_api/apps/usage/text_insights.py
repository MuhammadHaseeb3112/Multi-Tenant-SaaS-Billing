"""
"Text Insights" - the small demo product sold by the platform.

Pure, deterministic text statistics (no external services), so every
call is cheap and the interesting part of the project stays the
metering and billing around it.
"""

import math
import re
from collections import Counter


WORDS_PER_MINUTE = 200

STOP_WORDS = frozenset(
    """
    a about above after again all also am an and any are as at be because
    been before being below between both but by can could did do does doing
    down during each few for from further had has have having he her here
    hers him his how i if in into is it its itself just me more most my no
    nor not now of off on once only or other our ours out over own same she
    should so some such than that the their theirs them then there these
    they this those through to too under until up very was we were what
    when where which while who whom why will with would you your yours
    """.split()
)

WORD_RE = re.compile(r"[A-Za-z0-9']+")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]*")


def analyze_text(text, top_n=5):
    words = WORD_RE.findall(text)
    word_count = len(words)

    sentences = [
        s for s in SENTENCE_RE.findall(text) if WORD_RE.search(s)
    ]
    paragraphs = [
        p for p in re.split(r"\n\s*\n", text) if p.strip()
    ]

    keywords = Counter(
        w.lower().strip("'")
        for w in words
        if len(w) > 2 and w.lower().strip("'") not in STOP_WORDS
    )

    reading_seconds = (
        math.ceil(word_count * 60 / WORDS_PER_MINUTE)
        if word_count
        else 0
    )

    return {
        "characters": len(text),
        "characters_no_spaces": len(re.sub(r"\s", "", text)),
        "words": word_count,
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
        "average_word_length": (
            round(sum(len(w) for w in words) / word_count, 2)
            if word_count
            else 0
        ),
        "reading_time_seconds": reading_seconds,
        "top_keywords": [
            {"word": word, "count": count}
            for word, count in sorted(
                keywords.items(), key=lambda item: (-item[1], item[0])
            )[:top_n]
        ],
    }
