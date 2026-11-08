"""Turn messy free text into comparable forms.

Two forms are produced for every value:

* ``clean_text``: readable, kept in output for names no mapping covers yet
  ("  ameria   BANK " -> "Ameria Bank", "Ամերիա բանկ" -> "Amerya Bank").
* ``match_key``: aggressive, used only for matching
  ("<<Ameriabank>> CJSC" and "ameriabank" -> "ameriabank").
"""
import re
import unicodedata

# --- transliteration ---------------------------------------------------------------

_ARMENIAN_DIGRAPHS = {"ու": "u", "Ու": "U", "ՈՒ": "U"}
_ARMENIAN = {
    "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "e", "ը": "y", "թ": "t",
    "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "k", "հ": "h", "ձ": "dz", "ղ": "gh",
    "ճ": "ch", "մ": "m", "յ": "y", "ն": "n", "շ": "sh", "ո": "o", "չ": "ch", "պ": "p", "ջ": "j",
    "ռ": "r", "ս": "s", "վ": "v", "տ": "t", "ր": "r", "ց": "ts", "փ": "p", "ք": "q",
    "և": "ev", "օ": "o", "ֆ": "f", "ւ": "v",
    "Ա": "A", "Բ": "B", "Գ": "G", "Դ": "D", "Ե": "E", "Զ": "Z", "Է": "E", "Ը": "Y", "Թ": "T",
    "Ժ": "Zh", "Ի": "I", "Լ": "L", "Խ": "Kh", "Ծ": "Ts", "Կ": "K", "Հ": "H", "Ձ": "Dz", "Ղ": "Gh",
    "Ճ": "Ch", "Մ": "M", "Յ": "Y", "Ն": "N", "Շ": "Sh", "Ո": "O", "Չ": "Ch", "Պ": "P", "Ջ": "J",
    "Ռ": "R", "Ս": "S", "Վ": "V", "Տ": "T", "Ր": "R", "Ց": "Ts", "Փ": "P", "Ք": "Q",
    "Օ": "O", "Ֆ": "F", "Ւ": "V",
}
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
}
_CYRILLIC.update({k.upper(): v.capitalize() for k, v in list(_CYRILLIC.items())})
_LETTERS = {**_ARMENIAN, **_CYRILLIC}


def transliterate(text: str) -> str:
    """Armenian and Cyrillic -> Latin; accented Latin letters -> plain (é -> e)."""
    for src, dst in _ARMENIAN_DIGRAPHS.items():
        text = text.replace(src, dst)
    # Leftovers of letter-by-letter Armenian transliteration ("Latin o" + "ւ").
    text = text.replace("oւ", "u").replace("Oւ", "U")
    text = "".join(_LETTERS.get(ch, ch) for ch in text)
    folded = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# --- forms -------------------------------------------------------------------------

# Company legal forms, removed from match keys: "Ameriabank CJSC" == "Ameriabank".
LEGAL_SUFFIXES = {
    "llc", "ltd", "limited", "inc", "incorporated", "corp", "corporation", "co", "company",
    "plc", "gmbh", "ag", "sa", "sas", "srl", "spa", "bv", "nv", "oy", "ab", "as", "kft",
    "jsc", "cjsc", "ojsc", "pjsc", "ooo", "zao", "oao", "pao", "llp", "lp",
    "pby", "bby", "spy",  # Armenian ՓԲԸ, ԲԲԸ, ՍՊԸ after transliteration
}

_INVISIBLE = re.compile(r"[​‌‍⁠﻿]")
_SPACES = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def is_missing(value) -> bool:
    """None, NaN and pandas.NA (but not the text "nan" typed by a person)."""
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        return bool(value != value)  # NaN is the only value not equal to itself
    except TypeError:  # pandas.NA cannot be compared to a bool
        return True


def clean_text(value, transliterate_text: bool = True) -> str:
    """Readable cleaned form: invisible characters removed, single spaces, Title Case."""
    if is_missing(value):
        return ""
    text = _INVISIBLE.sub("", str(value))
    if transliterate_text:
        text = transliterate(text)
    return _SPACES.sub(" ", text).strip().title()


def match_key(value, transliterate_text: bool = True, drop_legal_suffixes: bool = True) -> str:
    """Aggressive matching form: lower case, no punctuation, no legal-form words."""
    text = clean_text(value, transliterate_text).lower()
    text = text.replace(".", "")  # "S.A." -> "sa", "Inc." -> "inc", "amazon.com" -> "amazoncom"
    text = _PUNCT.sub(" ", text)
    words = text.split()
    if drop_legal_suffixes:
        kept = [w for w in words if w not in LEGAL_SUFFIXES]
        words = kept or words  # never reduce a name to nothing ("Co" alone stays)
    return " ".join(words)
