"""Works out what a line of text means for the greenhouse assistant.

Everything the user says or types goes through handle_command(). Voice
input can be added later by feeding its text into this one function, so
the GUI never has to change.

handle_command() only ever SUGGESTS a plant. Making it the user's plant is
up to the user (the Plants page button, or confirming Sprout's suggestion).
"""
import re
from collections import namedtuple

from plant_db import list_plants

QUESTION_WORDS = {
    "what", "how", "why", "when", "where", "which", "who",
    "should", "can", "could", "is", "are", "does", "do", "will", "would",
}

# Wording that, BEFORE the plant's name, makes the text a plant choice:
# "I'm planting basil", "switch to tomatoes", "my plant is mint"
SELECT_WORDS = re.compile(
    r"\b(planting|growing|grow|plant|switch\s+to|change\s+to|select|choose"
    r"|my\s+plant\s+is)\b")

# Other names for plants (the plural rules below cover the usual forms)
ALIASES = {
    "pepper": "Bell Pepper",
    "peppers": "Bell Pepper",
    "capsicum": "Bell Pepper",
    "phalaenopsis": "Orchid",
    "orchids": "Orchid",
}

# kind: "select" (the text chooses a plant) or "ask" (send it to Sprout).
# plant: the plant mentioned, or None.
Command = namedtuple("Command", "kind plant")


def looks_like_question(text):
    words = re.findall(r"[a-z']+", text.lower())
    return "?" in text or (bool(words) and words[0] in QUESTION_WORDS)


def plural_forms(word):
    """The word and its plurals: tomato -> tomatoes, strawberry ->
    strawberries, cactus -> cacti / cactuses."""
    forms = {word, word + "s", word + "es"}   # +es also covers cactuses
    if word.endswith("y"):
        forms.add(word[:-1] + "ies")
    if word.endswith("us"):
        forms.add(word[:-2] + "i")
    return forms


def plant_forms():
    """(lowercase form, plant name) pairs, longest form first."""
    pairs = []
    for name in list_plants():
        *first_words, last_word = name.lower().split()
        for form in plural_forms(last_word):
            pairs.append((" ".join(first_words + [form]), name))
    pairs.extend(ALIASES.items())
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def _match_plant(text):
    """(plant name, start, end) of the plant mentioned in text, or None.
    Whole words only, so "peppermint" isn't Mint (or a pepper)."""
    text = text.lower()
    for form, name in plant_forms():
        words = r"\s+".join(re.escape(word) for word in form.split())
        match = re.search(r"\b" + words + r"\b", text)
        if match:
            return name, match.start(), match.end()
    return None


def find_plant(text):
    """Return the plant name mentioned in text, or None."""
    match = _match_plant(text)
    return match[0] if match else None


def handle_command(text):
    """Return a Command for the text.

    "select": a plant is mentioned and the text is just its name ("basil")
    or chooses it ("I'm planting basil"). No LLM call is needed.
    "ask": everything else (questions, "thanks", unknown plants), with the
    plant it mentions, if any.
    """
    match = _match_plant(text)
    if match is None:
        return Command("ask", None)
    plant, start, end = match
    lowered = text.lower()
    just_the_name = not re.search(r"\w", lowered[:start] + lowered[end:])
    chooses = (not looks_like_question(text)
               and SELECT_WORDS.search(lowered[:start]) is not None)
    if just_the_name or chooses:
        return Command("select", plant)
    return Command("ask", plant)


if __name__ == "__main__":
    # Quick self-test: python3 commands.py
    from plant_db import init_db
    init_db()
    for line in [
        "I'm planting basil",
        "growing Tomatoes this year",
        "strawberries",
        "switch to cacti",
        "what about bell peppers?",
        "Tell me about basil",
        "How humid should it be for lettuce",
        "my basil plant is wilting",
        "I'd like some peppermint tea",
        "I'm planting dragon fruit",
        "thanks",
    ]:
        print(repr(line), "->", handle_command(line))
