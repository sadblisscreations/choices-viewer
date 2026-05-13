"""Heuristic protobuf parser for Choices .protobin chapter files."""

from pathlib import Path

try:
    from google.protobuf.internal import decoder as _decoder
    _decode_varint = _decoder._DecodeVarint
except Exception:
    _decode_varint = None


def _read_varint(data: bytes, pos: int):
    """Read a varint from *data* at *pos*. Returns (value, new_pos)."""
    if _decode_varint is not None:
        return _decode_varint(data, pos)
    result = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos


def _parse_raw_node(data: bytes):
    """Parse a single protobuf message into a list of (field, wire_type, value)."""
    pos = 0
    out = []
    while pos < len(data):
        try:
            tag, pos = _read_varint(data, pos)
        except Exception:
            break
        field = tag >> 3
        wire = tag & 7
        if wire == 0:
            val, pos = _read_varint(data, pos)
            out.append((field, "v", val))
        elif wire == 1:
            out.append((field, "f64", data[pos : pos + 8]))
            pos += 8
        elif wire == 5:
            out.append((field, "f32", data[pos : pos + 4]))
            pos += 4
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            chunk = data[pos : pos + length]
            pos += length
            out.append((field, "bytes", chunk))
        else:
            break
    return out


def decode_protobin(path: Path):
    """Decode a .protobin file into (nodes, string_table)."""
    data = path.read_bytes()
    pos = 0
    top_fields = {}
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if wire == 0:
            val, pos = _read_varint(data, pos)
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            chunk = data[pos : pos + length]
            pos += length
            top_fields.setdefault(field, []).append(chunk)
        else:
            break

    if 7 not in top_fields:
        return [], []

    field7 = top_fields[7][0]
    pos = 0
    f7_fields = {}
    while pos < len(field7):
        tag, pos = _read_varint(field7, pos)
        field = tag >> 3
        wire = tag & 7
        if wire == 0:
            val, pos = _read_varint(field7, pos)
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        elif wire == 2:
            length, pos = _read_varint(field7, pos)
            chunk = field7[pos : pos + length]
            pos += length
            f7_fields.setdefault(field, []).append(chunk)
        else:
            break

    nodes = [_parse_raw_node(chunk) for chunk in f7_fields.get(5, [])]

    string_table = []
    for chunk in f7_fields.get(3, []):
        try:
            string_table.append(chunk.decode("utf-8"))
        except Exception:
            string_table.append(chunk.hex()[:20])

    return nodes, string_table


def _node_type(node) -> int:
    for field, t, val in node:
        if field == 1 and t == "v":
            return val
    return -1


def _node_text_index(node) -> int | None:
    for field, t, val in node:
        if field == 2 and t == "v":
            return val
    return None


def build_story(path: Path):
    """
    Build a simplified story representation from a .protobin file.
    Returns a list of story events:
        {"type": "dialog", "speaker": "...", "text": "...", "emotion": "...", "node_index": int}
        {"type": "choice", "options": [{"text": "...", "node_index": int}], "node_index": int}
        {"type": "break", "text": "...", "node_index": int}
    """
    nodes, string_table = decode_protobin(path)
    if not nodes:
        return []

    def text_of(node) -> str:
        idx = _node_text_index(node)
        if idx is not None and 0 <= idx < len(string_table):
            return string_table[idx]
        return ""

    node_types = [_node_type(n) for n in nodes]
    n = len(nodes)

    consumed = [False] * n
    choice_spans = []  # list of (start_index, end_index_exclusive, options_list)

    i = 0
    while i < n:
        if node_types[i] in (30, 31, 32):
            # Walk backwards to collect consecutive option blocks.
            j = i - 1
            raw_options = []
            while j >= 0:
                if node_types[j] != 20:
                    break
                break_idx = j
                if j - 1 < 0 or node_types[j - 1] != 41:
                    break
                texts = []
                k = j - 2
                while k >= 0 and node_types[k] == 25:
                    texts.append(text_of(nodes[k]))
                    k -= 1
                if not texts:
                    break
                texts.reverse()
                raw_options.insert(0, texts)
                for idx in range(k + 1, break_idx + 1):
                    consumed[idx] = True
                j = k

            consumed[i] = True
            footer_end = i + 1
            footer_types = [41, 50, 20, 51, 26, 4]
            for ft in footer_types:
                if footer_end < n and node_types[footer_end] == ft:
                    consumed[footer_end] = True
                    footer_end += 1

            scored = []
            for texts in raw_options:
                label = _pick_option_label(texts)
                score = _choice_option_score(texts)
                scored.append((score, label, texts))

            positive = [(s, l, t) for s, l, t in scored if s > 0]

            # If nothing scores positive, this "choice" is likely just conditional
            # dialog with no player-facing options. Skip it entirely.
            if positive:
                if len(positive) > 4:
                    positive = positive[-4:]

                real_opts = [{"text": _clean_text(label), "node_index": j + 1} for _s, label, _t in positive if label]
                real_opts = [o for o in real_opts if not _is_meta_option(o["text"])]
                real_opts = [o for o in real_opts if _is_meaningful_story_text(o["text"])]
                choice_spans.append((j + 1, footer_end, real_opts))
            i = footer_end
        else:
            i += 1

    # Build event list
    story = []
    i = 0
    while i < n:
        if consumed[i]:
            for start, end, opts in choice_spans:
                if i == start:
                    if opts:
                        story.append({"type": "choice", "options": opts, "node_index": start})
                    i = end
                    break
            else:
                i += 1
            continue

        typ = node_types[i]

        if typ == 25:
            texts = []
            first_idx = i
            while i < n and node_types[i] == 25:
                texts.append(text_of(nodes[i]))
                i += 1

            speaker, text, emotion = (_clean_text(v) for v in _extract_dialog(texts))
            if text and _is_meaningful_dialog(text, speaker, emotion):
                story.append({"type": "dialog", "speaker": speaker, "text": text, "emotion": emotion, "node_index": first_idx})
            continue

        if False:
            story.append({"type": "break", "text": "— break —", "node_index": i})
            i += 1
            continue

        i += 1

    # Post-process: keep reader-facing story beats only.
    filtered = []
    for ev in story:
        if ev["type"] == "choice" and not ev.get("options"):
            continue
        filtered.append(ev)

    for idx, ev in enumerate(filtered):
        title = ""
        if ev["type"] == "dialog":
            title = ev.get("text", "")
        elif ev["type"] == "choice":
            title = next((opt.get("text", "") for opt in ev.get("options", []) if opt.get("text", "").lower().startswith("chapter ")), "")
        if title.lower().startswith("chapter "):
            title_event = {"type": "dialog", "speaker": "", "text": title, "emotion": "", "node_index": ev.get("node_index", 0)}
            filtered = [title_event] + filtered[idx + 1:]
            break

    return filtered


def _clean_text(text: str) -> str:
    text = str(text or "").strip()
    for tag in ("cayenne", "premium", "choice", "b", "i"):
        text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return " ".join(text.split())


def _is_asset_or_var(text: str) -> bool:
    text = str(text or "").strip()
    low = text.lower()
    prefixes = (
        "IMG_", "BGZ_", "SFX_", "MUSIC_", "BOOK_VAR_",
        "PREM_", "OUTFIT_", "CUSTOM_ITEM_", "EFFECT_",
        "CLOSET_", "CCB_", "CCB_LAYER_", "TIMELINE_", "OVERLAY_",
        "ENV_", "BG_", "LI_", "EMOTE_", "BGM_",
    )
    if any(low.startswith(p.lower()) for p in prefixes):
        return True
    if low.startswith("book_var_") or low.startswith("assets/") or low.startswith("/assets/"):
        return True
    if low.endswith((".png", ".jpg", ".jpeg", ".plist", ".ccbi", ".ccb", ".mp3", ".m4a", ".wav")):
        return True
    if "/" in low or "\\" in low:
        return True
    if "_" in text and text.upper() == text and len(text) > 8:
        return True
    if "_" in low and any(part in low for part in ("portrait_", "item_", "particle", "neutral", "blocking")):
        return True
    return False


def _is_meta_option(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    meta = (
        "tap the arrows", "show female options", "show male options",
        "face 1", "face 2", "face 3",
    )
    return any(m in low for m in meta)


def _is_meaningful_story_text(text: str) -> bool:
    text = _clean_text(text)
    if not text or _is_asset_or_var(text):
        return False
    bare = text.lower()
    if bare in {"continue", "white", "black", "asian", "hispanic", "riley"}:
        return False
    if _looks_like_speaker(text):
        return False
    return len(text) > 3


def _is_meaningful_dialog(text: str, speaker: str, emotion: str) -> bool:
    if not text.strip():
        return False
    if _is_asset_or_var(text) or _is_asset_or_var(speaker):
        return False
    bare = text.strip().lower()
    if speaker.lower().startswith("enter the name"):
        return False
    # Skip bare speaker names, short tags, and UI words
    if bare in ("continue", "you", "c.man", "c.sir", "c.him", "c.her", "c.his") and not speaker and not emotion:
        return False
    if bare in ("white", "black", "asian", "hispanic", "riley"):
        return False
    if bare.startswith("what's your name?"):
        return False
    if _looks_like_speaker(text) and not speaker:
        return False
    words = text.strip().split()
    if (
        len(text) <= 32
        and words
        and words[0] in {"HAPPY", "SAD", "ANGRY", "SURPRISED", "NEUTRAL", "FLIRT", "FLIRTY", "SCARED"}
    ):
        return False
    if len(text) <= 30 and not speaker and not any(mark in text for mark in ".!?"):
        return False
    if len(text) <= 30 and text.endswith("Formal"):
        return False
    if len(bare) <= 3:
        return False
    return True


def _pick_option_label(texts: list[str]) -> str:
    if not texts:
        return ""
    for t in texts:
        t = _clean_text(t)
        if _is_meaningful_story_text(t):
            return t
    return _clean_text(texts[0])


def _sentence_count(text: str) -> int:
    """Rough sentence count that ignores ellipsis."""
    # Replace ellipsis with a single marker
    t = text.replace("...", "\x00")
    return t.count(".") + t.count("!") + t.count("?")


def _choice_option_score(texts: list[str]) -> int:
    if not texts:
        return -10

    primary = _clean_text(texts[0])
    if not primary:
        return -10

    score = 0

    # Length
    if len(primary) <= 50:
        score += 3
    elif len(primary) <= 80:
        score += 2
    elif len(primary) <= 110:
        score += 1
    elif len(primary) <= 130:
        score -= 2
    else:
        score -= 6

    # Dialog block detection
    if len(texts) >= 3:
        last = texts[-1].strip()
        if last.isupper() and len(last) <= 18 and " " not in last:
            score -= 8
    if len(texts) >= 2:
        second = texts[1].strip()
        if _looks_like_speaker(primary) and len(second) > len(primary):
            score -= 6

    # Narrative detection
    sentences = _sentence_count(primary)
    if sentences > 2:
        score -= 5
    if sentences > 1 and len(primary) > 100:
        score -= 4
    narrative_starts = (
        "the next evening", "for some reason", "there's a knock",
        "without even a glance", "your gaze drifts", "the woman shoots",
        "markus tosses you", "you turn the package",
    )
    low = primary.lower()
    if any(low.startswith(ns) for ns in narrative_starts):
        score -= 6

    # Choice-like indicators
    if primary.endswith("?"):
        score += 2
    choice_starts = (
        "i'll ", "i ", "my ", "me ", "take ", "kiss ", "tease ",
        "strip ", "chug ", "play ", "time to", "admit ", "surrender ",
        "but ", "just ", "like ", "because ", "how ", "what ", "who ",
        "when ", "where ", "why ", "never ", "distracted ", "seems ",
        "is too ", "removed ", "this takes ", "all loosened",
    )
    if any(low.startswith(cs) for cs in choice_starts):
        score += 2

    # Penalties
    if _is_asset_or_var(primary):
        score -= 10
    if primary.isupper() and len(primary) <= 18 and " " not in primary:
        score -= 10
    if _looks_like_speaker(primary) and len(primary) <= 12:
        score -= 8

    return score


def _looks_like_speaker(text: str) -> bool:
    text = text.strip()
    if len(text) > 20 or len(text) < 2:
        return False
    if " " in text or "." in text or "?" in text or "!" in text:
        return False
    return text[0].isupper() and all(c.isalpha() or c == "'" or c == "-" for c in text)


def _extract_dialog(texts: list[str]) -> tuple[str, str, str]:
    display = [_clean_text(t) for t in texts if _clean_text(t) and not _is_asset_or_var(t)]
    if not display:
        return "", "", ""

    speaker = ""
    text = ""
    emotion = ""

    if len(display) == 1:
        text = display[0]
    elif len(display) == 2:
        if display[1].isupper() and len(display[1]) <= 20 and " " not in display[1]:
            text = display[0]
            emotion = display[1]
        else:
            speaker = display[0]
            text = display[1]
    else:
        speaker = display[0]
        text = display[1]
        emotion = display[2] if len(display) > 2 else ""

    if emotion and (not emotion.isupper() or len(emotion) > 25 or " " in emotion):
        text = text + " " + emotion if text else emotion
        emotion = ""

    return speaker, text, emotion
