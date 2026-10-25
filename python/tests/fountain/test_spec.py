# This file is part of an MIT-licensed project: see LICENSE file or README.md for details.
# Copyright (c) 2024 Ian Thomas

# The fork's fixes, each against the Fountain spec (https://fountain.io/syntax): forced scene headings in any script,
# source line numbers, and the Writer writing back what the Parser reads.

import glob
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from screenplay_tools.fountain.parser import Parser
from screenplay_tools.fountain.writer import Writer
from screenplay_tools.screenplay import ElementType

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../tests"))


def parse(text):
    fp = Parser()
    fp.add_text(text)
    return fp.script


def fixtures():
    return [path for path in sorted(glob.glob(os.path.join(FIXTURES, "*.fountain"))) if "output" not in path]


class TestSpec(unittest.TestCase):

    def test_forced_scene_heading_in_any_script(self):
        # Scene Headings: "only a single leading period followed by an alphanumeric character will force a Scene Heading".
        for text, heading in ((".SNIPER SCOPE POV", "SNIPER SCOPE POV"), (".内景 茶馆 - 清晨", "内景 茶馆 - 清晨"),
                              (".Écurie - NUIT", "Écurie - NUIT"), (".1-2 #1-2#", "1-2")):
            with self.subTest(text):
                [element] = parse(text + "\n\nSomething happens.\n").elements[:1]
                self.assertEqual((element.type, element.text), (ElementType.HEADING, heading))
        for text in ("...where the second-rate carnival is parked.", ". NOT A HEADER", "._underscored"):
            with self.subTest(text):
                self.assertEqual(parse(text + "\n").elements[0].type, ElementType.ACTION)

    def test_every_element_has_the_line_it_starts_on(self):
        for path in fixtures():
            with open(path, encoding="utf-8") as file:
                source = file.read()
            lines = source.splitlines()
            script = parse(source)
            for element in [*script.titleEntries, *script.elements, *script.notes, *script.boneyards]:
                with self.subTest(file=os.path.basename(path), element=element.dump()[:60]):
                    self.assertIsNotNone(element.line)
                    first = (element.name if element.type == ElementType.CHARACTER else
                             element.key if element.type == ElementType.TITLEENTRY else
                             element.text.split("\n")[0]).replace("    ", "\t").strip()
                    # Notes and boneyards are taken out of the text they sit in.
                    line = lines[element.line - 1] if element.type in (ElementType.NOTE, ElementType.BONEYARD) else \
                        re.sub(r"\[\[.*?\]\]|/\*.*?\*/", "", lines[element.line - 1])
                    line = line.replace("    ", "\t")
                    if first:
                        self.assertIn(first, line)

    def test_line_numbers_count_every_line(self):
        script = parse("Title: A\n\nINT. HOUSE - DAY\n\nShe waits.\n\nDAN\n(quietly)\nHello.\n\n[[A note.]]\n")
        self.assertEqual([(e.type, e.line) for e in script.elements],
                         [(ElementType.HEADING, 3), (ElementType.ACTION, 5), (ElementType.CHARACTER, 7),
                          (ElementType.PARENTHETICAL, 8), (ElementType.DIALOGUE, 9), (ElementType.ACTION, 11)])
        self.assertEqual([(e.key, e.line) for e in script.titleEntries], [("Title", 1)])
        self.assertEqual([n.line for n in script.notes], [11])

    def test_text_around_a_note_or_boneyard_starts_where_it_opens(self):
        script = parse("INT. HOUSE - DAY\n\nShe waits. [[A note\nover two lines.]]\n\nDAN\nHello.\n\n/*\nCut.\n*/\n\nShe leaves.\n")
        self.assertEqual([(e.type, e.line) for e in script.elements if e.text.strip() or e.type != ElementType.ACTION],
                         [(ElementType.HEADING, 1), (ElementType.ACTION, 3), (ElementType.CHARACTER, 6),
                          (ElementType.DIALOGUE, 7), (ElementType.ACTION, 13)])
        self.assertEqual([(n.line, n.closed) for n in script.notes + script.boneyards], [(3, True), (9, True)])

    def test_an_unclosed_note_or_boneyard_is_marked(self):
        # Notes: "if you wish a note to contain an empty line, you must place two spaces there", so a blank line ends
        # an unclosed one; Boneyard: text is hidden "between /* and */", so the script's end ends an unclosed one.
        script = parse("INT. HOUSE - DAY\n\nShe waits. [[A note\n\nDAN\nHello.\n\n/* Cut from here.\n\nShe leaves.\n")
        self.assertEqual([(n.type, n.line, n.closed) for n in script.notes + script.boneyards],
                         [(ElementType.NOTE, 3, False), (ElementType.BONEYARD, 8, False)])

    def test_writer_writes_back_what_the_parser_reads(self):
        for path in fixtures():
            with self.subTest(os.path.basename(path)):
                with open(path, encoding="utf-8") as file:
                    script = parse(file.read())
                self.assertMultiLineEqual(script.dump(), parse(Writer().write(script)).dump())

    def test_forced_elements_keep_their_marks(self):
        # Character: "@" forces a character, "for non-Roman languages"; Dual Dialogue: "the caret is the last character
        # on the line"; Line Breaks: "!" forces an uppercase line to be Action.
        source = ("INT. HOUSE - DAY\n\n@林晚 (V.O.)\n你好。\n\nBRICK\nScrew it.\n\nSTEEL (O.S.) ^\nScrew it.\n\n"
                  "THE DEALER waits.\n\n!SCANNING THE AISLES...\nWhere is he?\n")
        written = Writer().write(parse(source))
        for line in ("@林晚 (V.O.)", "STEEL (O.S.) ^", "!SCANNING THE AISLES..."):
            self.assertIn(line, written)
        self.assertEqual(parse(written).dump(), parse(source).dump())


if __name__ == '__main__':
    unittest.main()
