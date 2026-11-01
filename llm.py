"""Talks to the local Ollama server (fully offline once the model is pulled).

ask() never raises: it returns (ok, text). If Ollama isn't running or is too
slow, ok is False and text is a short, readable error message, so the GUI
can just display it (and knows not to remember it as an answer).
"""
import json
import socket
import urllib.error
import urllib.request

import units
from plant_db import list_plants, get_plant

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"   # if the Pi is too slow, try "llama3.2:1b"
TIMEOUT_SECONDS = 180   # first request is slow while the model loads


def build_system_prompt(active_plant=None, reading=None):
    """Instructions + the plant table, so answers come from our database."""
    lines = []
    for name in list_plants():
        p = get_plant(name)
        lines.append(
            f"- {p['name']}: {units.ideal_ranges(p)}. {p['notes'] or ''}".rstrip()
        )
    table = "\n".join(lines)

    prompt = (
        "You are Sprout, the assistant in Green Gauge, a greenhouse climate monitor. "
        "Answer in at most 2 short sentences, in plain text with no markdown. "
        "For the plants in the reference table, use ONLY the ranges in the table. "
        "If a plant is not in the table, say it isn't in your database, then give "
        "a rough answer clearly labelled as general guidance. "
        "Temperatures are in °C and humidity is % relative humidity (RH).\n\n"
        f"Reference table (ideal ranges):\n{table}\n"
    )
    if active_plant:
        prompt += f"\nThe user is currently growing: {active_plant}."
    if reading:
        prompt += (
            f"\nCurrent greenhouse reading: {units.temperature(reading[0])}, "
            f"{units.humidity(reading[1])}."
        )
    return prompt


def build_messages(question, active_plant=None, reading=None, history=()):
    """System message, then the earlier (question, answer) pairs in order,
    then the new question."""
    messages = [{"role": "system",
                 "content": build_system_prompt(active_plant, reading)}]
    for earlier_question, earlier_answer in history:
        messages.append({"role": "user", "content": earlier_question})
        messages.append({"role": "assistant", "content": earlier_answer})
    messages.append({"role": "user", "content": question})
    return messages


def ask(question, active_plant=None, reading=None, history=()):
    """Send a question to the model. Returns (ok, text): the answer, or
    ok=False and an error message.

    history: earlier (question, answer) pairs, oldest first, so follow-up
    questions like "And what temperature?" make sense."""
    body = {
        "model": MODEL,
        "stream": False,
        "keep_alive": "10m",  # keep the model loaded between questions
        "options": {"temperature": 0.3, "num_predict": 120},
        "messages": build_messages(question, active_plant, reading, history),
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
        answer = data["message"]["content"].strip()
        if not answer:
            return False, "I didn't get an answer. Try rephrasing."
        return True, answer
    except (socket.timeout, TimeoutError):
        return False, "That took too long. The model may still be loading; try again."
    except urllib.error.HTTPError as error:
        # Ollama IS running but refused the request. HTTPError is a kind of
        # URLError, so it has to be checked first or it would be reported
        # as "can't reach Ollama".
        try:
            detail = json.load(error).get("error", "")
        except (ValueError, AttributeError):
            detail = ""
        if error.code == 404 or "not found" in detail.lower():
            return False, (f"Ollama is running, but the model {MODEL} isn't "
                           f"downloaded yet. In a terminal, run: ollama pull {MODEL}")
        return False, f"Ollama returned an error ({error.code}). {detail}".strip()
    except urllib.error.URLError:
        return False, ("Can't reach Ollama. Is it running? "
                       "(open the Ollama app, or run: ollama serve)")
    except (KeyError, TypeError, AttributeError, ValueError):
        return False, "Got an unexpected reply from Ollama."


if __name__ == "__main__":
    # Quick test: python3 llm.py
    from plant_db import init_db
    init_db()
    question = "What humidity does basil like?"
    ok, answer = ask(question, "Basil", (24.0, 60.0))
    print(ok, answer)
    if ok:   # a follow-up only makes sense with the first answer as context
        print(ask("And what temperature?", "Basil", (24.0, 60.0),
                  history=[(question, answer)]))
