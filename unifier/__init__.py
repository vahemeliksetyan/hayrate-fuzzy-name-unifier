"""Unify messy free-text names: company names, survey answers, universities, vendors, job titles."""
from unifier.mapping import Mapping, unmatched
from unifier.normalize import clean_text, match_key, transliterate
from unifier.suggest import suggest_groups

__all__ = ["Mapping", "unmatched", "clean_text", "match_key", "transliterate", "suggest_groups"]
__version__ = "1.0.0"
