"""Translations. Every text in the code is a text ID: tr("menu.quit") returns the text in the selected language.

Each language (German too) is a module g733_tray/lang/<code>.py with the dictionary STRINGS (key = text ID).
If an ID is missing in the selected language, the English text is shown; if it is missing there too, the ID itself.
N_("id") marks an ID for translation only (it is translated with tr() when displayed), e.g. for constants.
"""
import importlib
import logging

log = logging.getLogger("g733.i18n")

FALLBACK_LANGUAGE = "en"  # replacement for missing entries and when the system language is not offered
AUTO = "auto"

# language code -> native name (shown in the selection, each in its own language)
LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
    "ru": "Русский",
    "tr": "Türkçe",
    "zh": "简体中文",
    "ja": "日本語",
}

_catalog = {}
_fallback = {}
_current = FALLBACK_LANGUAGE


def N_(text_id):
    """Marks a text ID for translation without translating it now."""
    return text_id


def tr(text_id):
    try:
        return _catalog[text_id]
    except KeyError:
        return _fallback.get(text_id, text_id)


def current_language():
    return _current


def system_language():
    """Language code of the system language, otherwise English."""
    from PyQt6.QtCore import QLocale
    for tag in QLocale.system().uiLanguages():
        code = tag.replace("_", "-").split("-")[0].lower()
        if code in LANGUAGES:
            return code
    return FALLBACK_LANGUAGE


def resolve(setting):
    """"auto" -> system language; unknown codes -> English."""
    if setting == AUTO:
        return system_language()
    return setting if setting in LANGUAGES else FALLBACK_LANGUAGE


def _load(code):
    return importlib.import_module(f"{__package__}.lang.{code}").STRINGS


def set_language(setting):
    """Sets the language (code or "auto") and returns the code actually used."""
    global _catalog, _fallback, _current
    code = resolve(setting)
    fallback = _load(FALLBACK_LANGUAGE)
    try:
        catalog = _load(code)
    except (ImportError, AttributeError) as err:
        log.warning("language file %s not loadable: %s", code, err)
        code, catalog = FALLBACK_LANGUAGE, fallback
    _catalog, _fallback, _current = catalog, fallback, code
    return code


set_language(FALLBACK_LANGUAGE)  # until the program selects the language
