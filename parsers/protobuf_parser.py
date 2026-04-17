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

                real_opts = [{"text": label, "node_index": j + 1} for _s, label, _t in positive if label]
                real_opts = [o for o in real_opts if not _is_meta_option(o["text"])]
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

            speaker, text, emotion = _extract_dialog(texts)
            if text and _is_meaningful_dialog(text, speaker, emotion):
                story.append({"type": "dialog", "speaker": speaker, "text": text, "emotion": emotion, "node_index": first_idx})
            continue

        if typ == 20:
            story.append({"type": "break", "text": "— break —", "node_index": i})
            i += 1
            continue

        i += 1

    # Post-process
    filtered = []
    for ev in story:
        if ev["type"] == "break":
            if not filtered or filtered[-1]["type"] != "break":
                filtered.append(ev)
        else:
            filtered.append(ev)

    while filtered and filtered[0]["type"] == "break":
        filtered.pop(0)

    return filtered


def _is_asset_or_var(text: str) -> bool:
    prefixes = (
        "IMG_", "BGZ_", "SFX_", "MUSIC_", "BOOK_VAR_",
        "PREM_", "OUTFIT_", "CUSTOM_ITEM_", "EFFECT_",
        "CLOSET_",
    )
    return any(text.startswith(p) for p in prefixes)


def _is_meta_option(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    meta = (
        "tap the arrows", "show female options", "show male options",
        "face 1", "face 2", "face 3",
    )
    return any(m in low for m in meta)


def _is_meaningful_dialog(text: str, speaker: str, emotion: str) -> bool:
    if not text.strip():
        return False
    if _is_asset_or_var(text):
        return False
    bare = text.strip().lower()
    # Skip bare speaker names, short tags, and UI words
    if bare in ("continue", "you", "c.man", "c.sir", "c.him", "c.her", "c.his") and not speaker and not emotion:
        return False
    if len(bare) <= 3:
        return False
    return True


def _pick_option_label(texts: list[str]) -> str:
    if not texts:
        return ""
    for t in texts:
        if not _is_asset_or_var(t) and t.strip():
            return t
    return texts[0]


def _sentence_count(text: str) -> int:
    """Rough sentence count that ignores ellipsis."""
    # Replace ellipsis with a single marker
    t = text.replace("...", "\x00")
    return t.count(".") + t.count("!") + t.count("?")


def _choice_option_score(texts: list[str]) -> int:
    if not texts:
        return -10

    primary = texts[0].strip()
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
    display = [t for t in texts if not _is_asset_or_var(t)]
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
