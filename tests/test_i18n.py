import importlib
import re
import unittest
from unittest import mock

from g733_tray import i18n
from tests.i18n_extract import non_literal_calls, source_strings

PLACEHOLDER = re.compile(r"\{[^{}]*\}")
HTML_TAG = re.compile(r"</?[a-z]+>")
TEXT_ID = re.compile(r"[a-z0-9_]+(\.[a-z0-9_]+)+")


def catalog(code):
    return importlib.import_module(f"g733_tray.lang.{code}").STRINGS


class Catalogs(unittest.TestCase):
    def test_every_language_has_a_file(self):
        for code in i18n.LANGUAGES:
            self.assertTrue(catalog(code), code)

    def test_all_ids_present_and_none_stale(self):
        used = source_strings()
        for code in i18n.LANGUAGES:
            keys = set(catalog(code))
            self.assertEqual(sorted(used - keys), [], f"{code}: missing translations")
            self.assertEqual(sorted(keys - used), [], f"{code}: unused entries")

    def test_ids_have_the_expected_form(self):
        for text_id in source_strings():
            self.assertRegex(text_id, TEXT_ID)

    def test_placeholders_and_markup_match(self):
        reference = catalog(i18n.FALLBACK_LANGUAGE)
        for code in i18n.LANGUAGES:
            for text_id, text in catalog(code).items():
                self.assertEqual(sorted(PLACEHOLDER.findall(reference[text_id])), sorted(PLACEHOLDER.findall(text)),
                                 f"{code}: placeholders in {text_id}")
                self.assertEqual(sorted(HTML_TAG.findall(reference[text_id])), sorted(HTML_TAG.findall(text)),
                                 f"{code}: HTML tags in {text_id}")
                self.assertTrue(text.strip(), f"{code}: empty translation for {text_id}")

    def test_translations_format_with_their_placeholders(self):
        values = dict(version="4.2.0", installed="3.0.0", wanted="4.2.0", error="x", level=5, duration="1 h",
                      hours=2, minutes=3, name="G733", ids="046d:0ab5")
        for code in i18n.LANGUAGES:
            for text in catalog(code).values():
                text.format(**values)  # must not raise

    def test_non_literal_calls_are_known(self):
        # tr(label) / tr(self.problem) / tr(install_kind()): the IDs are in the catalog via N_()
        self.assertEqual(sorted(call.split(": ", 1)[1] for call in non_literal_calls()),
                         ["tr(install_kind())", "tr(label)", "tr(self.problem)"])


class Switching(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_switch(self):
        self.assertEqual(i18n.set_language("de"), "de")
        self.assertEqual(i18n.tr("menu.quit"), "Beenden")
        self.assertEqual(i18n.set_language("en"), "en")
        self.assertEqual(i18n.tr("menu.quit"), "Quit")
        self.assertEqual(i18n.set_language("xx"), "en")  # unknown -> English

    def test_missing_id_falls_back_to_english_then_to_the_id(self):
        i18n.set_language("de")
        with mock.patch.dict(i18n._catalog):
            del i18n._catalog["menu.quit"]
            self.assertEqual(i18n.tr("menu.quit"), "Quit")
        self.assertEqual(i18n.tr("no.such.id"), "no.such.id")

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
