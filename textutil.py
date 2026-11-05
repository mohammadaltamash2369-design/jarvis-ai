import re

_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())}
_NUMERIC = set(_UNITS) | set(_TENS)


def words_to_digits(text):
    """'timer for twenty five minutes' -> 'timer for 25 minutes'"""
    tokens = text.split()
    out, i = [], 0
    while i < len(tokens):
        if tokens[i] not in _NUMERIC:
            out.append(tokens[i])
            i += 1
            continue
        total = cur = 0
        j = i
        while j < len(tokens):
            w = tokens[j]
            if w in _UNITS:
                cur += _UNITS[w]
            elif w in _TENS:
                cur += _TENS[w]
            elif w == "hundred":
                cur = max(cur, 1) * 100
            elif w == "thousand":
                total += max(cur, 1) * 1000
                cur = 0
            elif w == "and" and j > i and j + 1 < len(tokens) and tokens[j + 1] in _NUMERIC:
                pass
            else:
                break
            j += 1
        out.append(str(total + cur))
        i = j
    return " ".join(out)


def humanize_seconds(s):
    parts = []
    for name, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        n, s = divmod(s, size)
        if n:
            parts.append(f"{n} {name}{'s' if n != 1 else ''}")
    if not parts:
        return "0 seconds"
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def parse_duration(text):
    total = 0
    for n, unit in re.findall(r"(\d+)\s*(hour|hr|minute|min|second|sec)", text):
        n = int(n)
        total += n * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1)
    return total
