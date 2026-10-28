import importlib
import re
import unittest

from g733_tray import i18n
from tests.i18n_extract import non_literal_calls, source_strings

PLACEHOLDER = re.compile(r"\{[^{}]*\}")
HTML_TAG = re.compile(r"</?[a-z]+>")
TRANSLATED = [code for code in i18n.LANGUAGES if code != i18n.SOURCE_LANGUAGE]


def catalog(code):
    return importlib.import_module(f"g733_tray.lang.{code}").STRINGS


class Catalogs(unittest.TestCase):
    def test_every_language_has_a_file(self):
        for code in TRANSLATED:
            self.assertTrue(catalog(code), code)

    def test_all_texts_translated_and_none_stale(self):
        source = source_strings()
        for code in TRANSLATED:
            keys = set(catalog(code))
            self.assertEqual(sorted(source - keys), [], f"{code}: fehlende Übersetzungen")
            self.assertEqual(sorted(keys - source), [], f"{code}: veraltete Einträge")

    def test_placeholders_and_markup_match(self):
        for code in TRANSLATED:
            for german, text in catalog(code).items():
                self.assertEqual(sorted(PLACEHOLDER.findall(german)), sorted(PLACEHOLDER.findall(text)),
                                 f"{code}: Platzhalter in {german!r}")
                self.assertEqual(sorted(HTML_TAG.findall(german)), sorted(HTML_TAG.findall(text)),
                                 f"{code}: HTML-Tags in {german!r}")
                self.assertTrue(text.strip(), f"{code}: leere Übersetzung für {german!r}")

    def test_translations_format_with_their_placeholders(self):
        values = dict(version="4.2.0", installed="3.0.0", wanted="4.2.0", error="x", level=5, duration="1 h",
                      hours=2, minutes=3, name="G733", ids="046d:0ab5")
        for code in TRANSLATED:
            for german, text in catalog(code).items():
                text.format(**values)  # darf nicht werfen

    def test_non_literal_calls_are_known(self):
        # tr(label) / tr(self.problem) / tr(install_kind()): die Texte stehen über N_() im Katalog
        self.assertEqual(sorted(call.split(": ", 1)[1] for call in non_literal_calls()),
                         ["tr(install_kind())", "tr(label)", "tr(self.problem)"])


class Switching(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("de")

    def test_switch_and_fallback(self):
        self.assertEqual(i18n.set_language("en"), "en")
        self.assertEqual(i18n.tr("Beenden"), "Quit")
        self.assertEqual(i18n.tr("Unbekannter Text"), "Unbekannter Text")  # fehlt: Originaltext
        self.assertEqual(i18n.set_language("de"), "de")
        self.assertEqual(i18n.tr("Beenden"), "Beenden")
        self.assertEqual(i18n.set_language("xx"), "en")  # unbekannt -> Englisch

    def test_every_language_loads(self):
        for code in i18n.LANGUAGES:
            self.assertEqual(i18n.set_language(code), code)

    def test_config_accepts_only_known_languages(self):
        import tempfile
        from pathlib import Path
        from g733_tray.config import Config
        with tempfile.TemporaryDirectory() as d:
            config = Config(Path(d) / "c.json")
            self.assertEqual(config["language"], "auto")
            config.update({"language": "FR"})
            self.assertEqual(config["language"], "fr")
            config.update({"language": "klingon"})
            self.assertEqual(config["language"], "auto")


if __name__ == "__main__":
    unittest.main()
