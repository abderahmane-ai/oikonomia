"""Build annotated.jsonl for the first 15 batch documents.

Spans are given as *surface strings in document order*, never as offsets: the
builder locates each one by scanning forward from the end of the previous span,
so an off-by-one is structurally impossible. Where a surface is ambiguous (a
bare "κ" that is a day number), a longer context string disambiguates it.
"""

import json
from pathlib import Path

# (label, surface, context|None, key|None) — document order, no overlaps.
E = lambda label, surface, ctx=None, key=None: (label, surface, ctx, key)  # noqa: E731
# (surface, reason, context|None) — a numeral deliberately left unlabelled.
# reason ∈ {isopsephism, sheet_number, line_reference, non_referential}.
S = lambda surface, reason, ctx=None: (surface, reason, ctx)  # noqa: E731

SPEC: dict[str, dict] = {}

SPEC["110220"] = {"entities": [
    E("PLACE", "Ῥώμης"),
    E("COMMODITY", "χλαμύδες χρωμάτιναι", None, "c1"),
    E("QUANTITY", "γ", "χρωμάτιναι γ", "q1"),
    E("COMMODITY", "μικρότερα", None, "c2"),
    E("QUANTITY", "α", "μικρότερα α", "q2"),
    E("COMMODITY", "λευκὰ", "λευκὰ α", "c3"),
    E("QUANTITY", "α", "λευκὰ α", "q3"),
    E("COMMODITY", "κολόβια λευκὰ", None, "c4"),
    E("QUANTITY", "β", "κολόβια λευκὰ β", "q4"),
    E("PLACE", "Ἀλεξάνδρειαν"),
    E("QUANTITY", "β", "τὰ πεμφθέντα β"),
    E("PERSON", "Ἀνεσίου"),
    E("COMMODITY", "κολόβια λευκὰ", None, "c5"),
    E("QUANTITY", "δ", "κολόβια λευκὰ δ", "q5"),
    E("COMMODITY", "ἀρρενικὰ", None, "c6"),
    E("QUANTITY", "α", "ἀρρενικὰ α", "q6"),
    E("PERSON", "Αἰλουρίωνος"),
    E("COMMODITY", "φαινόλης καλλάινος", None, "c7"),
    E("QUANTITY", "α", "καλλάινος α", "q7"),
    E("COMMODITY", "κολόβια λευκὰ Λαδικηνὰ", None, "c8"),
    E("QUANTITY", "α", "Λαδικηνὰ α", "q8"),
], "relations": [(f"c{i}", f"q{i}", "HAS_QUANTITY") for i in range(1, 9)]}

SPEC["11295"] = {"entities": [
    E("DATE_REF", "ὑπατείας", None, "date"),
    E("PERSON", "Μαξιμίνου"),
    E("PERSON", "Αὐρηλίων Γούνθου", None, "p_gounthos"),
    E("PERSON", "Αταρι", "καὶ Αταρι χωρὶς", "p_atari"),
    E("PERSON_ROLE", "χωρὶς κυρίου", None, "r_nokyrios"),
    E("PERSON", "Ατρεας", None, "p_atreas"),
    E("PERSON_ROLE", "μετὰ κυρίου"),
    E("PERSON", "Αὐρηλίου\nΝεμεσίωνος Ἰουλίου"),
    E("PERSON", "Θεοδώρας"),
    E("PERSON", "Ταύητος"),
    E("PERSON", "Σαμβαθοῦτος"),
    E("PERSON_ROLE", "ἀφηλίκων"),
    E("PERSON_ROLE", "μετὰ κυρίου"),
    E("PERSON", "Αὐρηλίου Γούνθου"),
    E("PERSON", "Παπνουθίου"),
    E("PERSON", "Τανίλλας"),
    E("PLACE", "κώμης Α…τ…"),
    E("PLACE", "Ἡρακλείδου μερίδος"),
    E("PLACE", "κώμῃ Φιλαδελφίᾳ"),
    E("COMMODITY", "οἰκίδιον μικρὸν μονόστεγον καὶ αὐλὴν", None, "house"),
    E("TRANSACTION", "ἐξοικονομοῦντες", None, "t1"),
    E("PERSON", "Αὐρηλίᾳ Ταπαϊτι", None, "p_buyer"),
    E("PERSON", "Πατερμουθίου"),
    E("PERSON", "Ταεισᾶτος"),
    E("PLACE", "κώμης Φιλαδελφίας"),
    E("PRICE_TERM", "τιμῆς"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "ταλάντου", None, "tal"),
    E("MONEY_AMOUNT", "ἑνὸς", None, "m1"),
    E("CURRENCY", "δραχμῶν", None, "dr"),
    E("MONEY_AMOUNT", "ἐνακοσίων", None, "m2"),
    E("PERSON", "Αὐρήλιοι Γοῦνθος"),
    E("PERSON", "Αταρις"),
    E("PERSON", "Ατρεα", "καὶ Ατρεα\n"),
    E("PERSON", "Ταύης"),
    E("PERSON", "Σαμβαθοῦς"),
    E("PERSON", "Αὐρηλίᾳ Ταπαϊτι"),
    E("COMMODITY", "οἰκίδιον καὶ αὐλὴν"),
], "relations": [
    ("m1", "tal", "HAS_CURRENCY"), ("m2", "dr", "HAS_CURRENCY"),
    ("house", "m1", "HAS_PRICE"), ("house", "m2", "HAS_PRICE"),
    ("p_gounthos", "t1", "PARTY_OF"), ("p_atari", "t1", "PARTY_OF"),
    ("p_atreas", "t1", "PARTY_OF"), ("p_buyer", "t1", "PARTY_OF"),
    ("r_nokyrios", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["114283"] = {"entities": [
    E("DATE_REF", "ὑπατείας"),
    E("PERSON", "Ὁνωρίου"), E("DATE_REF", "τὸ ι"),
    E("PERSON", "Θεοδοσίου"), E("DATE_REF", "τὸ ϛ"),
    E("DATE_REF", "Φαῶφι κα", None, "date"),
    E("PERSON", "Φλαουΐῳ Ἀντωνίῳ"),
    E("OCCUPATION", "σκρινιαρίῳ"),
    E("OCCUPATION", "κόμητος", "μεγαλοπρεπεστάτου κόμητος"),
    E("PERSON", "Ἰωάννου"),
    E("OCCUPATION", "βοηθοῦ"),
    E("PERSON", "Αὐρήλιος Ἄμμων", None, "p1"),
    E("TRANSACTION", "ὡμολόγησα", None, "t1"),
    E("PERSON", "Αὐρήλιος Ἄμμων"),
    E("CURRENCY", "χρυσοῦ"),
    E("CURRENCY", "νομισμάτιον", None, "nom"),
    E("MONEY_AMOUNT", "ἓν", None, "m1"),
    E("PERSON", "Αὐρήλιος Ἰωάννης"),
    E("OCCUPATION", "ἀναγνώστης"),
], "relations": [("m1", "nom", "HAS_CURRENCY"),
    ("p1", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO")]}

SPEC["115553"] = {"entities": [
    E("PLACE", "Κερκεῦρα"),
    E("PLACE", "Εἰρηναίου\nκλήρου"),
    E("DATE_REF", "ι ἔτους"),
    E("PERSON", "Ἀριστοῦτος"),
    E("PERSON", "Ἀπολλωνίου"),
    E("PLACE", "Ὀξυρύγχων πόλεως"),
    E("PLACE", "Κερκεμοῦνιν"),
    E("PLACE", "Φίλωνος κλήρου"),
    E("PERSON", "Ταβαροῦτος"),
    E("PERSON", "Ὥρου"),
    E("PERSON", "Ἀμόιντος", "καὶ Ἀμόιντος"),
    E("PERSON", "Παποντῶτος"),
    E("PERSON", "Διοδώρου"),
    E("PERSON", "Ταναεσνάως"),
    E("PERSON", "Πτολεμαίου"),
    E("PLACE", "Μερμέρθα"),
    E("PLACE", "Ἀνδρονίκου\nκλήρου"),
    E("DATE_REF", "ἔτους", "κλήρου … ἔτους"),
    E("PLACE", "Ὀξυρύγχων πόλεως"),
    E("PERSON", "Ἀσκλᾶτος Θοώνιος"),
    E("PERSON", "Ταθοωνᾶτος"),
    E("PERSON", "Σαραπίωνος"),
    E("PERSON", "Θοῶνις"),
], "relations": [],
    # bare δ opening the fragment, no governing noun survives the lacuna
    "skips": [S("δ", "non_referential", "…δ")]}

SPEC["1183"] = {"entities": [
    E("DATE_REF", "Ὑπερβερεταίου\nιη"),
    E("PERSON", "Ἀρτεμίδωρος"), E("OCCUPATION", "ἰατρός"),
    E("OCCUPATION", "ἱερεῖς", None, "occ1"), E("QUANTITY", "β", "ἱερεῖς β", "occq1"),
    E("COMMODITY", "Λευκαδίου", None, "c1"), E("UNIT", "κοτύλαι", None, "u1"),
    E("QUANTITY", "η", "κοτύλαι η", "q1"),
    E("DATE_REF", "ιθ", "ιθ Ἀρτεμίδωρος"),
    E("PERSON", "Ἀρτεμίδωρος"), E("OCCUPATION", "ἰατρός"),
    E("PERSON", "Ἀρτεμίδωρος"), E("OCCUPATION", "ἐπιστολογράφος"),
    E("PERSON", "Ἡφαιστίων"),
    E("OCCUPATION", "ἱερεῖς", None, "occ2"), E("QUANTITY", "γ", "ἱερεῖς γ", "occq2"),
    E("COMMODITY", "Λευκαδίου", None, "c2"), E("UNIT", "χοῦς", None, "u2"),
    E("QUANTITY", "α", "χοῦς α", "q2"),
    E("DATE_REF", "κ", "κ Ἀρτεμίδωρος"),
    E("PERSON", "Ἀρτεμίδωρος"), E("PERSON", "Ἡφαιστίων"), E("OCCUPATION", "ἱερεῖς"),
    E("COMMODITY", "οἴνου", None, "c3"), E("UNIT", "κοτύλαι", None, "u3"),
    E("QUANTITY", "η", "κοτύλαι η", "q3"),
    E("DATE_REF", "κα", "κα κατὰ πλοῦν"),
    E("PERSON", "Ἀρτεμιδώρωι"), E("PERSON", "Νικάνδρωι"), E("PERSON", "Θεοδώρωι"),
    E("UNIT", "κοτύλαι", None, "u4"), E("QUANTITY", "δ", "κοτύλαι δ", "q4"),
    E("PERSON", "Ἡροφάντωι"),
    E("UNIT", "κοτύλαι", None, "u5"), E("QUANTITY", "β", "κοτύλαι β", "q5"),
    E("DATE_REF", "κβ", "κβ ἐπὶ τοῦ ὅρμου"),
    E("PERSON", "Ἀρτεμίδωρος"), E("PERSON", "Ἰατροκλῆς"), E("PERSON", "Ἀρτεμίδωρος"),
    E("PERSON", "Δημήτριος"),
    E("UNIT", "χοῦς", None, "u6"), E("QUANTITY", "α", "χοῦς α", "q6"),
    E("PERSON", "Ἡρφάντωι"),
    E("DATE_REF", "κγ", "κγ Ἀρτεμίδωρος"), E("PERSON", "Ἀρτεμίδωρος"),
    E("DATE_REF", "κε", "κε εἰς κατάπλασμα"),
    E("COMMODITY", "κατάπλασμα", None, "c7"),
    E("UNIT", "κοτύλαι", None, "u7"), E("QUANTITY", "ε", "κοτύλαι ε", "q7"),
    E("PERSON", "Ἑρμίας"), E("PERSON", "Δημήτριος"),
    E("UNIT", "κοτύλαι", None, "u8"), E("QUANTITY", "ι", "κοτύλαι ι", "q8"),
    E("PERSON", "Ἡροφάντωι"),
    E("UNIT", "κοτύλαι", None, "u9"), E("QUANTITY", "β", "κοτύλαι β", "q9"),
    E("DATE_REF", "κϛ"),
    E("DATE_REF", "κζ", "κζ Δημητρίωι"), E("PERSON", "Δημητρίωι"),
    E("DATE_REF", "κζ", "κζ κη Ἀρτεμιδώρωι"),  # second day-marker in the diary
    E("DATE_REF", "κη", "κη Ἀρτεμιδώρωι"),
    E("PERSON", "Ἀρτεμιδώρωι"), E("OCCUPATION", "ἐπιστολογράφωι"),
    E("OCCUPATION", "ἱερεῦσι"), E("PERSON", "Ἑρμοφάντωι"),
    E("COMMODITY", "Κνιδίου", None, "c10"),
    E("UNIT", "κοτύλαι", None, "u10"), E("QUANTITY", "ϛ", "κοτύλαι ϛ", "q10"),
    E("DATE_REF", "κη", "κη κθ"),  # day-marker preceding κθ
    E("DATE_REF", "κθ", "κη κθ"),
    E("PERSON", "Πύρων"), E("PERSON", "Ἀμύντας"), E("PERSON", "Πάτρων"),
    E("COMMODITY", "κυβίων", None, "c11"),
    E("UNIT", "κεράμια", None, "u11"), E("QUANTITY", "β", "κεράμια β", "q11"),
    E("COMMODITY", "ἰσχάδων Ῥοδιακῶν", None, "c12"),
    E("UNIT", "κεράμια", None, "u12"), E("QUANTITY", "ε", "κεράμια ε", "q12"),
    E("COMMODITY", "Καυνίων", None, "c13"),
    E("UNIT", "κεράμια", None, "u13"), E("QUANTITY", "ε", "κεράμια ε", "q13"),
    E("COMMODITY", "τυροὺς Κυθνίους μεγάλους", None, "c14"),
    E("QUANTITY", "β", "μεγάλους β", "q14"),
    E("COMMODITY", "Ῥηναίους", None, "c15"), E("QUANTITY", "κ", "Ῥηναίους κ", "q15"),
    E("PERSON", "Ἀμύντου"),
    E("COMMODITY", "χλαμὺς\nπροβατεία"),
    E("COMMODITY", "οἴνου Χίου", None, "c16"),
    E("UNIT", "κεράμια", None, "u16"), E("QUANTITY", "β", "κεράμια β", "q16"),
], "relations": [
    ("occ1", "occq1", "HAS_QUANTITY"), ("occ2", "occq2", "HAS_QUANTITY"),
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("c3", "q3", "HAS_QUANTITY"), ("q3", "u3", "HAS_UNIT"),
    ("q4", "u4", "HAS_UNIT"), ("q5", "u5", "HAS_UNIT"), ("q6", "u6", "HAS_UNIT"),
    ("c7", "q7", "HAS_QUANTITY"), ("q7", "u7", "HAS_UNIT"),
    ("q8", "u8", "HAS_UNIT"), ("q9", "u9", "HAS_UNIT"),
    ("c10", "q10", "HAS_QUANTITY"), ("q10", "u10", "HAS_UNIT"),
    ("c11", "q11", "HAS_QUANTITY"), ("q11", "u11", "HAS_UNIT"),
    ("c12", "q12", "HAS_QUANTITY"), ("q12", "u12", "HAS_UNIT"),
    ("c13", "q13", "HAS_QUANTITY"), ("q13", "u13", "HAS_UNIT"),
    ("c14", "q14", "HAS_QUANTITY"), ("c15", "q15", "HAS_QUANTITY"),
    ("c16", "q16", "HAS_QUANTITY"), ("q16", "u16", "HAS_UNIT"),
]}

SPEC["11974"] = {"entities": [
    E("TRANSACTION", "ὁμολογία", None, "t1"),
    E("PERSON", "Παΰνχιος", None, "p1a"),
    E("PERSON_ROLE", "τῆς γυναικὸς", None, "p1b"),
    E("PERSON", "Πετεσοῦχον", None, "p1c"),
    E("CURRENCY", "δραχμῶν", None, "d1"), E("MONEY_AMOUNT", "ξδ", None, "m1"),
    E("CURRENCY", "ὀβολοὶ", None, "o1"), E("MONEY_AMOUNT", "ιε", None, "m2"),
    E("TRANSACTION", "ὁμολογία", None, "t2"),
    E("PERSON", "Ὀρσεῦτος", None, "p2a"),
    E("PERSON_ROLE", "τῆς γυναικὸς", None, "p2b"),
    E("PERSON", "Μαρεῦν", None, "p2c"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμῶν", None, "d2"), E("MONEY_AMOUNT", "κ", "δραχμῶν κ.", "m3"),
    E("CURRENCY", "ὀβολοὶ", None, "o2"), E("MONEY_AMOUNT", "η", "ὀβολοὶ η", "m4"),
    E("TRANSACTION", "μίσθωσις", None, "t3"),
    E("PERSON", "Ἡρακλήου", None, "p3a"),
    E("PERSON", "Δίδυμον Πασιουάνιος", None, "p3b"),
    E("COMMODITY", "ἀράκου", None, "c1"),
    E("UNIT", "ἀρούρης", None, "u1"), E("QUANTITY", "α", "ἀρούρης α", "q1"),
    E("FRACTION", "𐅵"),
    E("TRANSACTION", "ὁμολογία", None, "t4"),
    E("PERSON", "Θαυβάστεως", None, "p4a"),
    E("PERSON", "Τιεσιῆσιν", None, "p4b"),
    E("CURRENCY", "δραχμῶν", None, "d3"), E("MONEY_AMOUNT", "σ", "δραχμῶν σ", "m5"),
    E("PERSON", "Θερμοῦθιν"),
    E("COMMODITY", "κριθῆς", None, "c2"),
    E("UNIT", "ἀρτάβης", None, "u2"), E("QUANTITY", "α", "ἀρτάβης α", "q2"),
    E("TRANSACTION", "μίσθωσις", None, "t5"),
    E("PERSON", "Μάρωνος", None, "p5a"),
    E("PERSON", "Παποντῶν", None, "p5b"),
    E("UNIT", "ἀρουρῶν", None, "u3"), E("QUANTITY", "ια", "ἀρουρῶν ια", "q3"),
    E("CURRENCY", "δραχμαὶ", None, "d4"), E("MONEY_AMOUNT", "ϛ", "δραχμαὶ ϛ", "m6"),
    E("TRANSACTION", "μίσθωσις", None, "t6"),
    E("PERSON", "Ἡρᾶτος", None, "p6a"),
    E("PERSON", "Πάτρωνα", None, "p6b"),
    E("COMMODITY", "χλωρῶν", None, "c3"),
    E("UNIT", "ἀρουρῶν", None, "u4"), E("QUANTITY", "δ", "ἀρουρῶν δ", "q4"),
    E("TRANSACTION", "μίσθωσις", None, "t7"),
    E("PERSON", "Ψοσνεῦτος", None, "p7a"),
    E("PERSON", "Κρονίωνα", None, "p7b"),
    E("COMMODITY", "χόρτου", None, "c4"),
    E("UNIT", "ἀρουρῶν", None, "u5"), E("QUANTITY", "γ", "ἀρουρῶν γ", "q5"),
    E("COMMODITY", "χλωρῶν", None, "c5"),
    E("UNIT", "ἀρουρῶν", None, "u6"), E("QUANTITY", "γ", "ἀρουρῶν γ", "q6"),
    E("UNIT", "ἀρουρῶν", None, "u7"), E("QUANTITY", "ϛ", "ἀρουρῶν ϛ", "q7"),
    E("TRANSACTION", "δάνειον", None, "t8"),
    E("PERSON", "Μάρωνος", None, "p8a"),
    E("PERSON", "Ὀρσεῦν", None, "p8b"),
    E("PERSON_ROLE", "τὴν γυναῖκα", None, "p8c"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμῶν", None, "d5"), E("MONEY_AMOUNT", "μϛ", None, "m7"),
    E("CURRENCY", "ὀβολοὶ", None, "o3"), E("MONEY_AMOUNT", "ιδ", None, "m8"),
], "relations": [
    ("p1a", "t1", "PARTY_OF"),
    ("p1b", "t1", "PARTY_OF"),
    ("p1c", "t1", "PARTY_OF"),
    ("p2a", "t2", "PARTY_OF"),
    ("p2b", "t2", "PARTY_OF"),
    ("p2c", "t2", "PARTY_OF"),
    ("p3a", "t3", "PARTY_OF"),
    ("p3b", "t3", "PARTY_OF"),
    ("p4a", "t4", "PARTY_OF"),
    ("p4b", "t4", "PARTY_OF"),
    ("p5a", "t5", "PARTY_OF"),
    ("p5b", "t5", "PARTY_OF"),
    ("p6a", "t6", "PARTY_OF"),
    ("p6b", "t6", "PARTY_OF"),
    ("p7a", "t7", "PARTY_OF"),
    ("p7b", "t7", "PARTY_OF"),
    ("p8a", "t8", "PARTY_OF"),
    ("p8b", "t8", "PARTY_OF"),
    ("p8c", "t8", "PARTY_OF"),
    ("m1", "d1", "HAS_CURRENCY"), ("m2", "o1", "HAS_CURRENCY"),
    ("m3", "d2", "HAS_CURRENCY"), ("m4", "o2", "HAS_CURRENCY"),
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("m5", "d3", "HAS_CURRENCY"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("q3", "u3", "HAS_UNIT"), ("m6", "d4", "HAS_CURRENCY"),
    ("c3", "q4", "HAS_QUANTITY"), ("q4", "u4", "HAS_UNIT"),
    ("c4", "q5", "HAS_QUANTITY"), ("q5", "u5", "HAS_UNIT"),
    ("c5", "q6", "HAS_QUANTITY"), ("q6", "u6", "HAS_UNIT"),
    ("q7", "u7", "HAS_UNIT"),
    ("m7", "d5", "HAS_CURRENCY"), ("m8", "o3", "HAS_CURRENCY"),
]}

SPEC["12164"] = {"entities": [
    E("PERSON", "Ἡρακλείδης Ἡρακλείδου", None, "p1"),
    E("PERSON", "Κρονίωνι Ἀπίωνος", None, "p2"), E("OCCUPATION", "νομογράφωι"),
    E("PLACE", "Τεβτύνεως"),
    E("TRANSACTION", "ὁμολογῶ", None, "t1"),
    E("PERSON", "Ἡρακλείδην νεώτερον\nΜάρωνος"),
    E("UNIT", "ἀρουρῶν", None, "u1"), E("QUANTITY", "τριῶν", None, "q1"),
    E("FRACTION", "ἡμίσους"),
    E("PERSON", "Ἡρώδου τοῦ καὶ Ἡρακλείδου\nΛυσιμάχου"),
    E("DATE_REF", "ἔτους ὀγδόου", None, "date"),
    E("PERSON", "Τιβερίου Κλαυδίου Καίσαρος\nΣεβαστοῦ Γερμανικοῦ\nΑὐτοκράτορος"),
    E("DATE_REF", "Φαρμοῦθι ιδ"),
], "relations": [("q1", "u1", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO")]}

SPEC["12583"] = {"entities": [
    E("DATE_REF", "ἔτους τρεισκαιδεκάτου", None, "date"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Τίτου Αἰλίου Ἁδριανοῦ Ἀντωνίνου Σεβαστοῦ\nΕὐσεβοῦς"),
    E("DATE_REF", "μηνὸς Σεβαστοῦ κζ"), E("DATE_REF", "Θὼθ κζ"),
    E("PLACE", "Ἱερᾷ Νήσῳ"), E("PLACE", "Ἡρακλείδου μερίδος"), E("PLACE", "Ἀρσινοΐτου νομοῦ"),
    E("TRANSACTION", "ὁμολογεῖ", None, "t1"),
    E("PERSON", "Πτολεμαὶς Χαιρήμονος τοῦ Χαιρήμονος", None, "p_seller"),
    E("PLACE", "ἀμφόδου Φρεμεὶ"),
    E("AGE", "πεντήκοντα ὀκτὼ"),
    E("PERSON", "Κέλερος Ἀφροδισίου"),
    E("PERSON", "Ἰουλίῳ Μαξίμῳ", None, "p_lender"),
    # civic origin: an Antinoite of the Osirantinoeus deme (feeds geography)
    E("PLACE", "Ἀντινοεῖ", "καὶ Ἀντινοεῖ"), E("PLACE", "Ὀσιραντινοείῳ"),
    E("PERSON", "Πτολεμαΐδα"),
    E("PERSON", "Ἰουλίου Μαξίμου"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμὰς", None, "dr"),
    E("MONEY_AMOUNT", "ὀκτακοσίας", None, "m1"),
    E("PERSON", "Ἰούλιον Μάξιμον"),
    E("PERSON", "Πτολεμαΐδι"),
    E("PLACE", "κώμην Κερκεσοῦχαν"),
    E("UNIT", "ἀρουρῶν", None, "u1"), E("QUANTITY", "τεσσάρων", None, "q1"),
    E("UNIT", "ἀρουρῶν", None, "u2"), E("QUANTITY", "ἑπτὰ", None, "q2"),
    E("DATE_REF", "τρεισκαιδεκάτου ἔτους"),
    E("PERSON", "Ἀντωνίνου Καίσαρος"),
    E("PERSON", "Πτολεμαΐδα"),
    E("PERSON", "Ἰουλίῳ Μαξίμῳ"),
    E("UNIT", "ἀρούρας", None, "u3"), E("QUANTITY", "τέσσαρας", None, "q3"),
], "relations": [
    ("m1", "dr", "HAS_CURRENCY"),
    ("q1", "u1", "HAS_UNIT"), ("q2", "u2", "HAS_UNIT"), ("q3", "u3", "HAS_UNIT"),
    ("p_seller", "t1", "PARTY_OF"), ("p_lender", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["12593"] = {"entities": [
    E("COMMODITY", "νομῆς ὑπολόγων καὶ ῥαχοῦ", None, "c1"),
    E("PLACE", "Ψενύρεως"),
    E("CURRENCY", "δραχμῶν", None, "d1"), E("MONEY_AMOUNT", "κ", "δραχμῶν κ.", "m1"),
    E("PERSON", "Ἁρυώθου", None, "p1"),
    E("PLACE", "Ψενύρεως"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("DATE_REF", "ιη ἔτος"),
    E("PERSON", "Ἁδριανοῦ Καίσαρος"),
    E("COMMODITY", "νομὴν ὑπολόγων καὶ ῥαχοῦ", None, "c2"),
    E("PLACE", "Ψενύρεως"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμὰς", None, "d2"), E("MONEY_AMOUNT", "εἴκοσι", None, "m2"),
    E("PERSON", "Ἁρυώθης"),
    E("DATE_REF", "ἔτους ιζ", None, "date"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Τραϊανοῦ\nἉδριανοῦ Σεβαστοῦ"),
    E("DATE_REF", "Ἐπεὶφ η"),
    E("PERSON", "Βησαρίων"), E("OCCUPATION", "ὑπηρέτης"),
], "relations": [
    ("m1", "d1", "HAS_CURRENCY"), ("c1", "m1", "HAS_PRICE"),
    ("m2", "d2", "HAS_CURRENCY"), ("c2", "m2", "HAS_PRICE"),
    ("p1", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO"),
], "skips": [S("μϛ", "sheet_number", "κολλήματος μϛ")]}

SPEC["12769"] = {"entities": [
    E("PERSON", "Στοτοῆτι Στοτοήτεως", None, "p1"),
    E("PERSON", "Ὥρου τοῦ Τεσενούφεως τοῦ Τεσενούφεως", None, "p2"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("PLACE", "κώμῃ Ἡρακλείᾳ"),
    E("COMMODITY", "ἐλαιουργεῖον"),
    E("DATE_REF", "μηνὸς Σωτηρίου νουμηνίας"),
    E("DATE_REF", "πεντεκαιδεκάτου ἔτους", None, "date"),
    E("PERSON", "Αὐτοκράτορος\nΚαίσαρος Δομιτιανοῦ Σεβαστοῦ Γερμανικοῦ"),
    E("TAX_TERM", "φόρου"),
    E("COMMODITY", "ἐλαίου ῥαφανίνου", None, "c1"),
    E("UNIT", "μετρητῶν", None, "u1"), E("QUANTITY", "δύο", None, "q1"),
    E("COMMODITY", "ἐλαίου ῥαφανίνου"),
    E("PERSON", "Στοτοήτεως"),
], "relations": [("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO")]}

SPEC["128477"] = {"entities": [
    E("DATE_REF", "Παῦνι κθ"),
    E("DATE_REF", "Ἐπὶφ θ"), E("PLACE", "Καμμέτος"),
    E("COMMODITY", "σίτου", None, "c1"), E("UNIT", "ἀρτάβαι", None, "u1"),
    E("QUANTITY", "γ", "ἀρτάβαι γ", "q1"), E("FRACTION", "𐅷"),
    E("DATE_REF", "Ἐπὶφ ι"), E("PLACE", "Ἰερημίου"),
    E("COMMODITY", "σίτου", None, "c2"), E("UNIT", "ἀρτάβαι", None, "u2"),
    E("FRACTION", "𐅷"),
    E("DATE_REF", "Ἐπὶφ ιβ"), E("PLACE", "Τρακωνε"),
    E("COMMODITY", "σίτου", None, "c3"), E("UNIT", "ἀρτάβαι", None, "u3"),
    E("QUANTITY", "ε", "ἀρτάβαι ε", "q3"),
    E("DATE_REF", "Ἐπὶφ ιε"),
    E("PLACE", "Καμμέτος"), E("PLACE", "Τρακωνη"), E("PLACE", "Τιμε"),
    E("COMMODITY", "σίτου", None, "c4"), E("UNIT", "ἀρτάβαι", None, "u4"),
    E("QUANTITY", "δ", "ἀρτάβαι δ", "q4"),
    E("DATE_REF", "Ἐπὶφ κθ"),
    E("PLACE", "Νέου", "τόπου Νέου"),  # place-name (partly lost: Νέου … Λάκκου)
    E("COMMODITY", "σίτου", None, "c5"), E("UNIT", "ἀρτάβαι", None, "u5"),
    E("QUANTITY", "β", "ἀρτάβαι β", "q5"),
    E("PLACE", "Μοιρῶν"),
    E("COMMODITY", "σίτου", None, "c6"), E("UNIT", "ἀρτάβαι", None, "u6"),
    E("FRACTION", "𐅷"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c3", "q3", "HAS_QUANTITY"), ("q3", "u3", "HAS_UNIT"),
    ("c4", "q4", "HAS_QUANTITY"), ("q4", "u4", "HAS_UNIT"),
    ("c5", "q5", "HAS_QUANTITY"), ("q5", "u5", "HAS_UNIT"),
]}

SPEC["13473"] = {"entities": [
    E("PERSON", "Τασεῦς"), E("OCCUPATION", "ἀρχιπροφήτης"),
    E("PLACE", "Ἡλίου πόλει"),
    E("PERSON", "Ὥρου Ἀρήιτος"), E("OCCUPATION", "ἱερέως"),
    E("PERSON", "Νεβωνυχος Ἰφύνους"), E("OCCUPATION", "ἱερεὺς"),
    E("OCCUPATION", "δευτεροστολιστὴς"),
    E("PERSON", "Πετοσορᾶπις Πετοσοράπιος"), E("OCCUPATION", "λεσώνης"),
    E("PERSON", "Σερῆνος Μενθώτου"), E("OCCUPATION", "ἱερεῖς"),
    E("PERSON", "Μάρωνι Πακήβκεως τοῦ καὶ Ζωσίμου"), E("OCCUPATION", "ἱερεῖ"),
    E("PLACE", "κώμης Τεπτύνεως"), E("PLACE", "Πολέμωνος μερίδος"),
    E("PLACE", "Ἀρσινοείτου νομοῦ"),
    E("PERSON", "Διοσκόρου\nἈπολλωνίου"),
    E("COMMODITY", "βυσσοῦ", None, "c1"),
    E("UNIT", "πήχεις", None, "u1"), E("QUANTITY", "εἴκοσι", None, "q1"),
    E("DATE_REF", "ἔτους ιθ"),
    E("PERSON", "Μάρκου Αὐρηλίου\nἈντωνίνου"),
    E("PERSON", "Πουβλίου Σεπτιμίου Γέτα"),
], "relations": [("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT")]}

SPEC["13487"] = {"entities": [
    E("PERSON", "Ἀντωνίωι Μοσχιανῶι Οὐλπιανῶι"), E("OCCUPATION", "ἐπιστρατηγῶι"),
    E("PERSON", "Θέωνος Μάρωνος"), E("PLACE", "Ἀρσινοίτου"),
    E("PERSON", "Ἰνσταντίου Μοδεράτου"),
    E("COMMODITY", "πυροῦ"),
    E("DATE_REF", "λα ἔτει μηνὶ Μεσορὴ"),
    E("OCCUPATION", "γραμματέων"),
], "relations": []}

SPEC["144620"] = {"entities": [
    E("PERSON", "Ψενθώτης"), E("OCCUPATION", "κονδούκτωρι"),
    E("PLACE", "Διδύμου ὑδρεύματος"),
    E("PERSON", "Κάλβῳ"), E("PERSON", "Σιουῆτι"),
    E("COMMODITY", "κριθῆς", None, "c1"),
    E("UNIT", "μάτια", None, "u1"), E("QUANTITY", "τέσσαρα", None, "q1"),
    E("QUANTITY", "δ", "γίνεται δ"),
    E("COMMODITY", "ἄρτων", None, "c2"),
    E("UNIT", "ζεύγη", None, "u2"), E("QUANTITY", "ὀκτὼ", None, "q2"),
    E("QUANTITY", "η", "γίνεται η"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
]}

SPEC["144885"] = {"entities": [
    E("PERSON", "Ἰούλιος"), E("PERSON", "Ἀντωνίωι"),
    E("CURRENCY", "στατῆρα"),
    E("PERSON", "Οὐαλερίου"),
    E("CURRENCY", "ὀβόλους", None, "ob"), E("MONEY_AMOUNT", "ε", "ὀβόλους ε", "m1"),
    E("PERSON", "Κέλερος"), E("OCCUPATION", "ἱππέως"),
    E("COMMODITY", "ἁλός"),
], "relations": [("m1", "ob", "HAS_CURRENCY")]}


# ---------------------------------------------------------------------------
# Batch documents 16-30 (index 15-29). Same method, calibrated to guidelines
# v0.2: TRANSACTION anchors, PERSON_ROLE for unnamed/role parties, rulers split
# out of DATE_REF, mothers annotated as PERSON, genitive-named parcels PLACE.
# ---------------------------------------------------------------------------

SPEC["14562"] = {"entities": [  # census/epikrisis age-list
    E("DATE_REF", "β ἔτους"),
    E("DATE_REF", "ια ἔτους", "ια ἔτους. οἱ"),
    E("DATE_REF", "τὸ η ἔτος"),
    E("AGE", "ιβ", "ἐτῶν ιβ"),
    # tally of how many were aged 12 (counted head — ephebes — elided)
    E("QUANTITY", "β", "ἐτῶν ιβ β"),
    E("AGE", "ιδ", "ἐτῶν ιδ"),
    E("PERSON", "Ὀννῶφρις Τιθοήους"), E("PERSON", "Ἐσενεῦτος"),
    E("PERSON", "Νεστνηώρου", "Νεστνηώρου μητρὸς"),  # father of a damaged-name registrant
    E("PERSON", "Ταακείους"),
    E("PERSON", "Παποντῶς Νεφερῶτος"), E("PERSON", "Ἡρῶτος"),
    E("DATE_REF", "θ ἔτει"),
    E("PERSON", "Κιαλῆς ὃς καὶ Νεφερῶς Νεφερῶτος"), E("PERSON", "Ταήσιος"),
    E("DATE_REF", "ια ἔτους", "ια ἔτους. …"),
    E("DATE_REF", "ι ἔτους", "ι ἔτους. ο…"),
    E("DATE_REF", "ι ἔτους", "ι ἔτους ……"),
    E("DATE_REF", "θ ἔτους"),
], "relations": []}

SPEC["15074"] = {"entities": [  # livestock (camel) declaration + purchase
    E("PLACE", "Σοκνοπαίου Νήσου"),
    E("COMMODITY", "κάμηλος", "Σοκνοπαίου Νήσου κάμηλος", "c0"),
    E("QUANTITY", "α", "κάμηλος α\n", "q0"),
    E("PERSON", "Θεοδώρωι"), E("OCCUPATION", "στρατηγῷ"),
    E("PERSON", "Τειμαγένει"), E("OCCUPATION", "βασιλικῷ γραμματεῖ"),
    E("PLACE", "Ἀρσινοίτου"), E("PLACE", "Ἡρακλείδου μερίδος"),
    E("PERSON", "Ἑκύσιος Ὥρου", None, "declarant"),
    E("PLACE", "κώμης Σοκνοπαίου Νήσου"),
    E("DATE_REF", "κ ἔτους"),
    E("COMMODITY", "θρεμμάτων"),
    E("TRANSACTION", "ἠγόρασα", None, "t1"),
    E("PERSON", "Πτολεμαίου\nΛεωνίδου", None, "seller"),
    E("PLACE", "κώμης Καρανίδος"),
    E("COMMODITY", "κάμηλον", None, "c1"), E("QUANTITY", "μίαν", None, "q1"),
    E("OCCUPATION", "στρατηγῷ", "παρὰ στρατηγῷ"),
    E("OCCUPATION", "βοηθοῦ", "βοηθοῦ κάμηλος"),
    E("COMMODITY", "κάμηλος", "βοηθοῦ κάμηλος", "c2"), E("QUANTITY", "α", "κάμηλος α Μεχεὶρ", "q2"),
    E("DATE_REF", "Μεχεὶρ γ", "κάμηλος α Μεχεὶρ γ"),
    E("OCCUPATION", "βασιλικῷ", "παρὰ βασιλικῷ κάμηλος"),
    E("COMMODITY", "κάμηλος", "βασιλικῷ κάμηλος", "c3"), E("QUANTITY", "α", "κάμηλος α Μεχεὶρ", "q3"),
    E("DATE_REF", "Μεχεὶρ γ", "κάμηλος α Μεχεὶρ γ"),
    E("PERSON", "Πτολεμαῖος", "Πτολεμαῖος·"),
    E("OCCUPATION", "βασιλικῷ γραμματεῖ", "παρὰ βασιλικῷ γραμματεῖ"),
    E("PERSON", "Νεῖλος ὁ καὶ Σαπ"), E("OCCUPATION", "ἀγορανομήσας"),
    E("PERSON", "Ἰσιδώρου"), E("OCCUPATION", "βοηθοῦ", "Ἰσιδώρου βοηθοῦ"),
], "relations": [
    ("c0", "q0", "HAS_QUANTITY"), ("c1", "q1", "HAS_QUANTITY"),
    ("c2", "q2", "HAS_QUANTITY"), ("c3", "q3", "HAS_QUANTITY"),
    ("declarant", "t1", "PARTY_OF"), ("seller", "t1", "PARTY_OF"),
]}

SPEC["15090"] = {"entities": [  # property registration by a woman with guardian
    E("DATE_REF", "Μεχεὶρ κ", "Μεχεὶρ κ\n"),
    E("PERSON", "Ἀπολλωνίῳ"), E("OCCUPATION", "γεγυμνασιαρχηκότι"),
    E("PERSON", "Νικολάῳ"), E("OCCUPATION", "βιβλιοφύλαξι ἐνκτήσεων"),
    E("PLACE", "Ἀρσινοΐτου"),
    E("PERSON", "Στοτοήτιος", "παρὰ Στοτοήτιος", "woman"),
    E("PERSON", "Στοτοήτιος τοῦ Ὥρου"),
    E("PLACE", "Σοκνοπαίου Νήσου"), E("PLACE", "Ἡρακλείδου μερίδος"),
    E("PERSON_ROLE", "μετὰ κυρίου τοῦ ἀνδρὸς"),
    E("PERSON", "Στοτοήτιος\nτοῦ Νεστνήφιος"),
    E("PERSON", "Ἀμμωνίου"), E("PERSON", "Σαραπίωνος"),
    E("DATE_REF", "ζ ἔτει", None, "date1"), E("PERSON", "Νέρωνος"),
    E("TRANSACTION", "ἐκτησάμην", None, "t1"),
    E("FRACTION", "ἥμισυ"), E("COMMODITY", "οἰκίας", None, "house"),
    E("PRICE_TERM", "τιμῆς"), E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμῶν", None, "dr"),
    E("MONEY_AMOUNT", "ἑκατὸν τεσσαράκοντα", None, "m1"),
    E("PERSON", "Ἐριέως\nτοῦ Ὀννώφριος τοῦ Ἁρπαγάθου", None, "seller"),
    E("OCCUPATION", "ἱερέως"),
    E("DATE_REF", "ἔτους δεκάτου"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος\nΟὐεσπασιανοῦ Σεβαστοῦ"),
    E("DATE_REF", "Μεχεὶρ κ", "Σεβαστοῦ Μεχεὶρ κ"),
], "relations": [
    ("m1", "dr", "HAS_CURRENCY"), ("house", "m1", "HAS_PRICE"),
    ("woman", "t1", "PARTY_OF"), ("seller", "t1", "PARTY_OF"),
    ("t1", "date1", "DATED_TO"),
]}

SPEC["15362"] = {"entities": [  # lease of an oil-press
    E("DATE_REF", "ὑπατείαν"), E("PERSON", "Ὁνωρίου"), E("DATE_REF", "τὸ θ"),
    E("PERSON", "Θεοδοσίου"), E("DATE_REF", "τὸ δ"),
    E("DATE_REF", "Θὼθ ιδ"),
    E("PERSON", "Φλαουΐῳ Λιμενίῳ", None, "lessor"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλεως"),
    E("PERSON", "Αὐρηλίου Πέτρου", None, "lessee"),
    E("OCCUPATION", "ἐλαιουργοῦ"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("DATE_REF", "Θὼθ", "μηνὸς Θὼθ τοῦ"),
    # Oxyrhynchite double era-year (89 = 58)
    E("DATE_REF", "ἔτους\nπθ νη", "ἐνεστῶτος ἔτους\nπθ νη"),
    E("DATE_REF", "ἑνδεκάτης ἰνδικτίωνος"),
    E("PLACE", "Παρεμβολῆς"),
    E("COMMODITY", "ἐλαιούργιον"),
    E("TAX_TERM", "φόρου"),
    E("COMMODITY", "ἐλαίου ῥαφανίνου", None, "c1"),
    E("UNIT", "ξέστας", None, "u1"), E("QUANTITY", "ἑκατὸν εἴκοσι", "ξέστας ἑκατὸν εἴκοσι", "q1"),
    E("UNIT", "ἀρτάβας", None, "u2"),
    E("QUANTITY", "ἑκατὸν εἴκοσι", "ἀρτάβας ἑκατὸν εἴκοσι", "q2"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("q2", "u2", "HAS_UNIT"),
    ("lessor", "t1", "PARTY_OF"), ("lessee", "t1", "PARTY_OF"),
]}

SPEC["15382"] = {"entities": [  # list of councillors present
    E("PERSON", "Ἑρμαίου"), E("PERSON", "Μοσχίων"),  # names in the damaged preamble
    E("DATE_REF", "λ τοῦ ὄντος μηνὸς Θὼθ"),
    E("DATE_REF", "ιδ ἔτους"),
    E("PERSON", "Ἀντωνίνου Καίσαρος"),
    E("PERSON", "Πολυδεύκης Ἡρακλείου"),
    E("PERSON", "Διονύσιος Ὅπλωνος"),
    E("PERSON", "Ἀνδρέας Ἀσκληπιάδου"),
    E("PERSON", "Ἰούλιος Νουμισιανὸς"),
    E("PERSON", "Ἡρακλείδης Γαίου"),
    E("PERSON", "Σωτάδης Διοδώρου υἱοῦ\nἈπολλωνίου"),
    E("PERSON", "Ἀθηνόδωρος ὁ καὶ Τούρβων"),
    E("PERSON", "Ἡρακλείου Ἀπολλοδώρου"),
    E("PERSON", "Εὐτυχίδης Σαραπίωνος"),
    E("PERSON", "Ἰούλιος", "Λο…\nἸούλιος"),  # damaged tail of the councillor list
    E("PERSON", "Ἰούλιος"),
], "relations": []}

SPEC["15454"] = {"entities": [  # loan / release (homologia)
    E("DATE_REF", "ὑπατείας"),
    E("PERSON", "Φλαουίων\nἈναστασίου"),
    E("PERSON", "Ῥούφου"),
    E("DATE_REF", "Ἁθὺρ ιβ"),
    E("DATE_REF", "α\nἰνδικτίονος"),
    E("PLACE", "κώμῃ Βουσίρει"),
    E("PERSON", "Αὐρήλιος\nἈβραὰμ υἱὸς\nΕὐδαίμονος", None, "p1"),
    E("PLACE", "κώμης Βουσίρεως"),
    E("PLACE", "Ἡρακλεουπολίτου νομοῦ"),
    E("PERSON", "Αὐρηλίῳ\nΔωροθέῳ υἱῷ Ψίωλ", None, "p2"),
    E("TRANSACTION", "ὁμολογῶ", None, "t1"),
    E("MONEY_AMOUNT", "κ", "τῶν κ κερατίων", "m1"), E("CURRENCY", "κερατίων", None, "cur1"),
    E("CURRENCY", "νομίσματα", "τὰ νομίσματα β\n", "cur2"), E("MONEY_AMOUNT", "β", "νομίσματα β\n", "m2"),
    E("CURRENCY", "νομίσματα", "ἐδεξάμην\nτὰ νομίσματα β", "cur3"), E("MONEY_AMOUNT", "β", "τὰ νομίσματα β καὶ", "m3"),
    E("PERSON", "Αὐρήλιος\nἌεις Κουαντίνου"),
    E("PERSON", "Ἄειτος Κουαντίνου"),
    # closing recap restates the two parties by name
    E("PERSON", "Ἀβραὰμ υἱὸς Εὐδαίμονος", "ἀμεριμνία Ἀβραὰμ υἱὸς Εὐδαίμονος"),
    E("PERSON", "Δωρόθεον υἱῷ Ψίωλ"),
    E("DATE_REF", "α ἰνδικτίονος"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"),
]}

SPEC["15488"] = {"entities": [  # loan of silver (blind); borrower's name lost to lacuna
    E("DATE_REF", "ὑπατείαν", None, "date"),
    E("PERSON", "Κωνσταντίνου"), E("PERSON", "Λικιννιανοῦ"),
    E("DATE_REF", "τὸ γ"),
    E("PERSON", "Πτολέμας"),
    E("PLACE", "Ὀξυρυγχίτου νομοῦ"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλεως"),
    E("TRANSACTION", "ὁμολογῶ", None, "t1"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "τάλαντα", None, "cur1"), E("MONEY_AMOUNT", "ἐννέα", None, "m1"),
    E("CURRENCY", "δραχμὰς", None, "cur2"),
    E("DATE_REF", "η ἔτους"), E("DATE_REF", "ϛ ἔτους"),
    E("CURRENCY", "μνᾶς"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"),
    ("t1", "date", "DATED_TO"),  # parties are lost to the lacuna; only the date survives
]}

SPEC["15887"] = {"entities": [  # payment order (blind)
    E("DATE_REF", "κδ ἔτους"), E("PERSON", "Ἀντωνίνου Καίσαρος"),
    E("DATE_REF", "Φαμενὼθ"),
    E("PERSON", "Ἰουλίων Θέωνος"), E("OCCUPATION", "ἐνάρχου\nἀρχιδικαστοῦ"),
    E("PERSON", "Θέωνος τοῦ καὶ\nΤρύφωνος"),
    E("TAX_TERM", "ὀψωνίου"),
    E("DATE_REF", "μηνὸς Ἁδριανοῦ"), E("DATE_REF", "Μεχείρ", "ἕως Μεχείρ"),
    # salary for a duration of 3 months
    E("UNIT", "μηνῶν", None, "um"), E("QUANTITY", "γ", "μηνῶν γ", "qm"),
    E("CURRENCY", "δραχμὰς", None, "cur1"), E("MONEY_AMOUNT", "ἑκατὸν εἴκοσι", None, "m1"),
    E("CURRENCY", "δραχμαὶ", None, "cur2"), E("MONEY_AMOUNT", "ρκ", "δραχμαὶ ρκ", "m2"),
    E("CURRENCY", "δραχμὰς", "τὰς δραχμὰς", "cur3"), E("MONEY_AMOUNT", "ρκ", "δραχμὰς ρκ", "m3"),
], "relations": [
    ("qm", "um", "HAS_UNIT"),
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"),
]}

SPEC["16001"] = {"entities": [  # lease / sworn cultivation undertaking (blind)
    E("DATE_REF", "ὑπατείαν"),
    E("PERSON", "Λικινίου Σεβαστοῦ"), E("DATE_REF", "τὸ ϛ"),
    E("PERSON", "Λικινίου\nτοῦ ἐπιφανεστάτου Καίσαρος"), E("DATE_REF", "τὸ β"),
    E("DATE_REF", "τὸ β", "ὑπάτοις τὸ β"),  # post-consular iteration figure
    E("PERSON", "Οὐάλεντι"),
    E("PERSON", "Αὐρήλιοι Πανοτβέως Ὀρσενούφιος", None, "p1"), E("PERSON", "Ταᾶτος"),
    E("PERSON", "Ἀφύγχις Ἀφυγχίου", None, "p2"), E("PERSON", "Θαήσιος"),
    E("PLACE", "κώμης Ποσόμπους"),
    E("PLACE", "Ὀξυρυγχίτου νομοῦ"),
    E("PERSON", "Κοπρεὺς Διοσκόρου", None, "p3"), E("PERSON", "Τενγώγιος"),
    E("PLACE", "Ποσόμπους κώμῃ"),
    E("TRANSACTION", "ὁμολογοῦμεν", None, "t1"),
    E("PERSON", "Πανοτβέουν"),
    E("UNIT", "ἀρουρῶν", "τὸν Πανοτβέουν\nἀρουρῶν", "u1"),
    E("QUANTITY", "ἑπτὰ", "ἀρουρῶν ἑπτὰ", "q1"), E("FRACTION", "ἡμίσους", "ἑπτὰ ἡμίσους"),
    E("PERSON", "Θερμούθει"), E("PERSON", "Θαισοῦτι"),
    E("PERSON", "Ἀφύγχιον"), E("PERSON", "Κοπρέα"),
    E("UNIT", "ἀρουρῶν", "ἑτέρων ἀρουρῶν", "u2"),
    E("QUANTITY", "ἑπτὰ", "ἑτέρων ἀρουρῶν ἑπτὰ", "q2"), E("FRACTION", "ἡμίσους", "ἀρουρῶν ἑπτὰ ἡμίσους"),
    E("UNIT", "ἀρούρας", None, "u3"), E("QUANTITY", "δεκαπέντε", None, "q3"),
    E("PERSON", "Κορνηλίου"),
    E("PERSON", "Θερμούτιον"), E("PERSON", "Θαισοῦν"),
    E("TAX_TERM", "φόρῳ"),
    E("PERSON", "Κοπρεὺς", "καὶ Κοπρεὺς"),  # second mention in the damaged closing
    E("PERSON", "Αὐρήλιος", "ὡμολογήσαμεν. Αὐρήλιος"),  # subscription writer
], "relations": [
    ("q1", "u1", "HAS_UNIT"), ("q2", "u2", "HAS_UNIT"), ("q3", "u3", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("p3", "t1", "PARTY_OF"),
    # "ε πάγου" — the 5th pagus, an administrative-district ordinal, not a quantity
], "skips": [S("ε", "non_referential", "Ποσόμπους ε πάγου")]}

SPEC["16015"] = {"entities": [  # census/epikrisis petition (girl's age)
    E("PERSON", "Αὐρηλίαν Ἀπίαν", None, "girl"),
    E("DATE_REF", "η ἔτος"), E("DATE_REF", "ζ ἔτος", "καὶ ζ ἔτος"),
    E("AGE", "ιη", "ἐτῶν ιη"),
    E("DATE_REF", "ἔτους η", "ἐψεῦσθαι. ἔτους η"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Γαΐου Αὐρηλίου\nΟὐαλερίου Διοκλητιανοῦ"),
    E("DATE_REF", "ζ ἔτους", "καὶ ζ ἔτους"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Μάρκου Αὐρηλίου\nΟὐαλερίου Μαξιμιανοῦ"),
    E("DATE_REF", "Παῦνι κζ"),
    E("PERSON", "Αὐρήλιος Σαραπίων", None, "father"),
    E("PERSON", "Παμμένους Παραδείσου"),
    E("PERSON", "Ἀπία", "Παραδείσου Ἀπία", "girl2"), E("PERSON", "Ἰσιδώρας"),
    E("AGE", "ιη", "ἐτῶν ιη\nφυσικὴ"),
    E("PERSON", "Σαραπίωνος", "θυγάτηρ Σαραπίωνος"),
], "relations": []}

SPEC["16219"] = {"entities": [  # Byzantine/Arab-era gold account
    E("PERSON", "Ὡρουγχίῳ"), E("OCCUPATION", "βοηθῷ"),
    E("PERSON", "Μαγίστωρ", "Ι Μαγίστωρ"), E("OCCUPATION", "βοηθὸς λογιστηρίου"),
    E("DATE_REF", "δευτέρας ἰνδικτίονος"),
    E("CURRENCY", "χρυσοῦ", "ὑποδοχῆς δευτέρας ἰνδικτίονος\nχρυσοῦ", "cur1"),
    E("CURRENCY", "νομίσματα", "χρυσοῦ νομίσματα ἓξ", "cur1b"),
    E("MONEY_AMOUNT", "ἓξ", "νομίσματα ἓξ εὔσταθμα", "m1"),
    E("PLACE", "Ἀλεξανδρείας", "εὔσταθμα Ἀλεξανδρείας"),
    E("PERSON", "Βασιλείῳ"), E("OCCUPATION", "βοηθῷ", "Βασιλείῳ βοηθῷ"),
    E("DATE_REF", "α ἰνδικτίονος"),
    E("PERSON", "Βίκτορος Διοσκ"), E("PERSON", "Ἰσιδώρου"),
    E("CURRENCY", "κεράτια", "Ἰσιδώρου κεράτια", "cur2"),
    E("MONEY_AMOUNT", "εἴκοσι τρία", None, "m2"),
    E("PLACE", "Ἀλεξανδρείας", "εἴκοσι τρία Ἀλεξανδρείας"),
    E("PLACE", "μοναστηρίου ἄπα Ἰακκώβου"),
    E("CURRENCY", "νομισμάτων", None, "cur3"), E("MONEY_AMOUNT", "ϛ", "νομισμάτων ϛ", "m3"),
    E("CURRENCY", "κεράτια", "ϛ κεράτια ιζ", "cur4"),
    E("MONEY_AMOUNT", "ιζ", "κεράτια ιζ 𐅵", "m4"), E("FRACTION", "𐅵", "ιζ 𐅵 κεράτια"),
    # "κεράτια δεκαεπτὰ ἥμισυ" restates ιζ 𐅵 in words (same 17½ carats); annotate
    # the value once (the figures above), keep the place qualifier here.
    E("PLACE", "Ἀλεξανδρείας", "ἥμισυ Ἀλεξανδρείας"),
    E("CURRENCY", "νομίσματα", "ὁμοῦ νομίσματα ζ", "cur5"),
    E("MONEY_AMOUNT", "ζ", "νομίσματα ζ κεράτια", "m5"),
    E("CURRENCY", "κεράτια", "νομίσματα ζ κεράτια ιϛ", "cur6"),
    E("MONEY_AMOUNT", "ιϛ", "κεράτια ιϛ 𐅵 Ἀλεξανδρείας\nἀφʼ", "m6"), E("FRACTION", "𐅵", "ιϛ 𐅵 Ἀλεξανδρείας\nἀφʼ"),
    E("PLACE", "Ἀλεξανδρείας", "𐅵 Ἀλεξανδρείας\nἀφʼ"),
    E("PERSON", "Μηνᾷ"), E("OCCUPATION", "ὑποδέκτῃ"),
    E("CURRENCY", "νόμισμα", None, "cur7"), E("MONEY_AMOUNT", "α", "νόμισμα α εὔσταθμον", "m7"),
    E("PLACE", "Ἀλεξανδρείας", "εὔσταθμον Ἀλεξανδρείας"),
    # remainder line: 6 solidi 16½ carats
    E("CURRENCY", "νομίσματα", "λοιπόν νομίσματα ϛ", "cur8"),
    E("MONEY_AMOUNT", "ϛ", "λοιπόν νομίσματα ϛ κεράτια", "m8"),
    E("CURRENCY", "κεράτια", "λοιπόν νομίσματα ϛ κεράτια", "cur9"),
    E("MONEY_AMOUNT", "ιϛ", "ϛ κεράτια ιϛ 𐅵 Ἀλεξανδρείας\nὑπὲρ", "m9"),
    E("FRACTION", "𐅵", "ιϛ 𐅵 Ἀλεξανδρείας\nὑπὲρ"),
    E("PLACE", "Ἀλεξανδρείας", "𐅵 Ἀλεξανδρείας\nὑπὲρ"),
    E("DATE_REF", "β ἰνδικτίονος", "αὐτῆς β ἰνδικτίονος"),
    E("DATE_REF", "Τῦβι ε ἰνδικτίονος β", "ἐγράφη Τῦβι ε ἰνδικτίονος β"),
    E("PERSON", "Μαγίστωρ", "… Μαγίστωρ σὺν"),
    E("OCCUPATION", "βοηθὸς λογιστηρίου", "θεῷ βοηθὸς λογιστηρίου ἐπιδέδωκα"),
    # "ἐπιδέδωκα" payment: 6 solidi 16½ carats
    E("CURRENCY", "χρυσοῦ", "ἐπιδέδωκα χρυσοῦ νομίσματα"),
    E("CURRENCY", "νομίσματα", "ἐπιδέδωκα χρυσοῦ νομίσματα ϛ", "cur10"),
    E("MONEY_AMOUNT", "ϛ", "χρυσοῦ νομίσματα ϛ κεράτια", "m10"),
    E("CURRENCY", "κεράτια", "νομίσματα ϛ κεράτια ιϛ 𐅵 Ἀλεξανδρείας\nἐντάγιον", "cur11"),
    E("MONEY_AMOUNT", "ιϛ", "ϛ κεράτια ιϛ 𐅵 Ἀλεξανδρείας\nἐντάγιον", "m11"),
    E("FRACTION", "𐅵", "ιϛ 𐅵 Ἀλεξανδρείας\nἐντάγιον"),
    E("PLACE", "Ἀλεξανδρείας", "𐅵 Ἀλεξανδρείας\nἐντάγιον"),
    E("PERSON", "Μαγίστωρος"),
    E("DATE_REF", "β ἰνδικτίονος", "Μαγίστωρος β ἰνδικτίονος"),
    # last line: 7 solidi 16½ carats
    E("CURRENCY", "χρυσοῦ", "ἰνδικτίονος χρυσοῦ νομίσματα ζ"),
    E("CURRENCY", "νομίσματα", "χρυσοῦ νομίσματα ζ κεράτια", "cur12"),
    E("MONEY_AMOUNT", "ζ", "νομίσματα ζ κεράτια ιϛ 𐅵 Ἀλεξανδρείας", "m12"),
    E("CURRENCY", "κεράτια", "ζ κεράτια ιϛ 𐅵 Ἀλεξανδρείας", "cur13"),
    E("MONEY_AMOUNT", "ιϛ", "κεράτια ιϛ 𐅵 Ἀλεξανδρείας", "m13"),
    E("FRACTION", "𐅵", "ιϛ 𐅵 Ἀλεξανδρείας"),
    E("PLACE", "Ἀλεξανδρείας", "𐅵 Ἀλεξανδρείας"),
], "relations": [
    ("m1", "cur1b", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"), ("m4", "cur4", "HAS_CURRENCY"),
    ("m5", "cur5", "HAS_CURRENCY"), ("m6", "cur6", "HAS_CURRENCY"),
    ("m7", "cur7", "HAS_CURRENCY"), ("m8", "cur8", "HAS_CURRENCY"),
    ("m9", "cur9", "HAS_CURRENCY"), ("m10", "cur10", "HAS_CURRENCY"),
    ("m11", "cur11", "HAS_CURRENCY"), ("m12", "cur12", "HAS_CURRENCY"),
    ("m13", "cur13", "HAS_CURRENCY"),
]}

SPEC["16396"] = {"entities": [  # order to grain-officials to release wheat
    E("PERSON", "Ἰσιδώρα Ἡροδώρου", None, "p1"),
    E("PERSON", "Διονυσίου\nτοῦ καὶ Ὠριγένους Διογένους"),
    E("OCCUPATION", "σιτολόγοις"),
    E("PLACE", "Ἄνω\nτοπαρχίας"),
    E("TRANSACTION", "διαστείλατε", None, "t1"),
    E("COMMODITY", "πυροῦ", None, "c1"),
    E("DATE_REF", "ια ἔτους", "γενήματος ια ἔτους"),
    E("PERSON", "Ἀντωνείνου\nΚαίσαρος", "ια ἔτους Ἀντωνείνου\nΚαίσαρος"),
    E("PERSON", "Ἡραΐδι\nΔιονυσίου", None, "p2"),
    E("UNIT", "ἀρτάβας", None, "u1"), E("QUANTITY", "ἕνδεκα", None, "q1"),
    E("UNIT", "χοίνικας", None, "u2"), E("QUANTITY", "ὀκτώ", None, "q2"),
    E("UNIT", "ἀρτάβαι", None, "u3"), E("QUANTITY", "ια", "ἀρτάβαι ια", "q3"),
    E("UNIT", "χοίνικες", None, "u4"), E("QUANTITY", "η", "χοίνικες η", "q4"),
    E("DATE_REF", "ἔτους ια", "ἔτους ια Ἀντωνείνου"),
    E("PERSON", "Ἀντωνείνου\nΚαίσαρος", "ἔτους ια Ἀντωνείνου\nΚαίσαρος"),
    E("DATE_REF", "Θὼθ", "κυρίου, Θὼθ"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("q2", "u2", "HAS_UNIT"),
    ("q3", "u3", "HAS_UNIT"), ("q4", "u4", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"),
]}

SPEC["16499"] = {"entities": [  # account of purchases/prices (damaged)
    E("DATE_REF", "μῆνα Παῦνι", "διελθόντα μῆνα Παῦνι"),
    E("PRICE_TERM", "τιμὴ", "Παῦνι τιμὴ δραχμαὶ"),
    E("CURRENCY", "δραχμαὶ", "τιμὴ δραχμαὶ ξ", "cur1"), E("MONEY_AMOUNT", "ξ", "δραχμαὶ ξ", "m1"),
    E("PERSON", "Ἰσχυρίωνος Διοσκοῦτος"), E("OCCUPATION", "γεγυμνασιαρχηκότος"),
    E("PLACE", "Ἀρσινοίτου"),
    E("COMMODITY", "γῆς ψιλῶν τόπων"),
    E("PERSON", "Τιβερίου Ποσιδωνίου τοῦ καὶ\nἸσχυρίωνος"),
    E("PERSON", "Κόθυς Ἀλεξανδρέως"),
    E("PLACE", "Ἀλεξανδρείας"),
    E("DATE_REF", "κα ἔτει"), E("DATE_REF", "Παῦνι", "μηνὶ Παῦνι τιμὴ"),
    E("PRICE_TERM", "τιμὴ", "Παῦνι τιμὴ δραχμαὶ ιδ"),
    E("CURRENCY", "δραχμαὶ", "τιμὴ δραχμαὶ ιδ", "cur2"), E("MONEY_AMOUNT", "ιδ", "δραχμαὶ ιδ", "m2"),
    E("CURRENCY", "δραχμαὶ", "δραχμαὶ υμ", "cur3"), E("MONEY_AMOUNT", "υμ", "δραχμαὶ υμ", "m3"),
    E("QUANTITY", "ζ", "ζ δραχμαὶ ιϛ"),  # count of a lost commodity priced at 16 dr
    E("CURRENCY", "δραχμαὶ", "ζ δραχμαὶ ιϛ", "cur4"), E("MONEY_AMOUNT", "ιϛ", "δραχμαὶ ιϛ", "m4"),
    E("CURRENCY", "δραχμαὶ", "ἀγαθων δραχμαὶ λϛ", "cur5"), E("MONEY_AMOUNT", "λϛ", "δραχμαὶ λϛ", "m5"),
    E("CURRENCY", "δραχμαὶ", "λϛ\nδραχμαὶ ιγ", "cur6"), E("MONEY_AMOUNT", "ιγ", "δραχμαὶ ιγ\n", "m6"),
    E("CURRENCY", "δραχμαὶ", "… δραχμαὶ ιγ", "cur7"), E("MONEY_AMOUNT", "ιγ", "δραχμαὶ ιγ\nεἰς", "m7"),
    E("PERSON", "Πτολεμαίδα"),
    E("PERSON", "Πτολεμαίου τοῦ Πτολεμαίου", "προ Πτολεμαίδα\nΠτολεμαίου τοῦ Πτολεμαίου"),
    E("CURRENCY", "δραχμῶν", "κεφαλαίου δραχμῶν ω", "cur8"), E("MONEY_AMOUNT", "ω", "δραχμῶν ω", "m8"),
    E("CURRENCY", "δραχμῶν", "τόκων δραχμῶν λβ", "cur9"), E("MONEY_AMOUNT", "λβ", "δραχμῶν λβ", "m9"),
    E("CURRENCY", "δραχμαὶ", "δραχμαὶ ωλβ", "cur10"), E("MONEY_AMOUNT", "ωλβ", "δραχμαὶ ωλβ", "m10"),
    E("CURRENCY", "δραχμαὶ", "ωλβ ἐπιδ δραχμαὶ κ", "cur11"), E("MONEY_AMOUNT", "κ", "δραχμαὶ κ\n", "m11"),
    E("PERSON", "Ἀπολλ Ἀνουβίωνος"),
    E("CURRENCY", "δραχμαὶ", "Ἀνουβίωνος δραχμαὶ η", "cur12"), E("MONEY_AMOUNT", "η", "δραχμαὶ η\n", "m12"),
    E("PERSON", "Πτολεμαὶς Πτολεμαίου τοῦ Πτολεμαίου"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"), ("m4", "cur4", "HAS_CURRENCY"),
    ("m5", "cur5", "HAS_CURRENCY"), ("m6", "cur6", "HAS_CURRENCY"),
    ("m7", "cur7", "HAS_CURRENCY"), ("m8", "cur8", "HAS_CURRENCY"),
    ("m9", "cur9", "HAS_CURRENCY"), ("m10", "cur10", "HAS_CURRENCY"),
    ("m11", "cur11", "HAS_CURRENCY"), ("m12", "cur12", "HAS_CURRENCY"),
]}

SPEC["16690"] = {"entities": [  # land lease
    E("TRANSACTION", "ἐμίσθωσαν", None, "t1"),
    E("PERSON", "Σαραπίων ὁ καὶ Ἀχιλλεὺς Ζωίλου", None, "lessor1"),
    E("PERSON", "Σαρούβων Σερήνου τοῦ\nκαὶ Πετρωνιανοῦ", None, "lessor2"),
    E("PLACE", "Ὀξυρύγχων πόλεως"),
    E("PERSON", "Ἕλληνι Φειβάστοῦ", None, "lessee"), E("PERSON", "Θαήσιως"),
    E("PLACE", "κώμης Παείμεως"),
    E("DATE_REF", "ἔτη δύο", "εἰς\nἔτη δύο"),
    E("DATE_REF", "ιγ ἔτους"),
    E("PLACE", "Παεῖμιν"),
    E("UNIT", "ἀρούρας", None, "u1"),
    E("QUANTITY", "δύας\nτέταρτον", "ἀρούρας δύας\nτέταρτον", "q1"),
    E("COMMODITY", "πυροῦ", "ἐκφορίου\nἀποτάκτου κατʼ ἔτος πυροῦ", "c1"),
    E("UNIT", "ἀρταβῶν", None, "u2"),
    E("QUANTITY", "δέκα τεσσάρων", "ἀρταβῶν\nδέκα τεσσάρων", "q2"),
    E("DATE_REF", "Παῦνι", "μηνὶ Παῦνι"),  # delivery month
    E("COMMODITY", "πυρὸν νέον καθαρὸν ἄδολον"),
    E("DATE_REF", "ἔτους ιγ", "μίσθωσις. ἔτους ιγ"),
    E("PERSON", "Λουκίου Σεπτιμίου\nΣεουήρου"),
    E("PERSON", "Μάρκου Αὐρηλίου\nἈντωνίνου"),
    E("PERSON", "Πουβλίου Σεπτιμίου Γέτα"),
    E("DATE_REF", "Φαῶφι κη"),
    E("PERSON", "Ἕλλην Φειβάστου"),
    E("COMMODITY", "γῆν", "τὴν γῆν"),
    E("DATE_REF", "ἔτη δύο", "εἰς τὰ ἔτη δύο"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("c1", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("lessor1", "t1", "PARTY_OF"), ("lessor2", "t1", "PARTY_OF"),
    ("lessee", "t1", "PARTY_OF"),
]}

SPEC["17157"] = {"entities": [  # sale of a female donkey
    E("PERSON", "Αὐρήλιος Κάστωρ Πεουῆτος", None, "seller"), E("PERSON", "Θαισοῦτος"),
    E("PLACE", "κώμης\nΘαλλοῦ"),
    E("PLACE", "Ἑρμοπολίτου νομοῦ"),
    E("PERSON", "Αὐρηλίῳ Ἑρμῇ Ἀνουβᾶτος", None, "buyer"), E("PERSON", "Δημητροῦτος"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλεως"),
    E("TRANSACTION", "πέπρακά", None, "t1"),
    E("PLACE", "Ὀξυρυγχίτην"),
    E("COMMODITY", "ὄνον θήλειαν μυόχροον\nτελείαν", None, "c1"),
    E("PRICE_TERM", "τιμῆς"),
    E("CURRENCY", "ἀργυρίου σεβαστῶν νομίσματος"),
    E("CURRENCY", "τάλαντον", "νομίσματος τάλαντον ἓν", "cur1"),
    E("MONEY_AMOUNT", "ἓν", "τάλαντον ἓν γίνεται", "m1"),
    E("CURRENCY", "τάλαντον", "γίνεται τάλαντον α", "cur2"), E("MONEY_AMOUNT", "α", "τάλαντον α\n", "m2"),
    E("COMMODITY", "ὄνον", "τὴν δʼ αὐτὴν ὄνον"),
    E("DATE_REF", "ἔτους ζ"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Γαίου\nΑὐρηλίου Οὐαλερίου Διοκλητιανοῦ"),
    E("DATE_REF", "ἔτους ϛ", "καὶ ἔτους ϛ"),
    E("PERSON", "Μάρκου Αὐρηλίου\nΟὐαλερίου Μαξιμιανοῦ"),
    E("PERSON", "Αὐρήλιος Κάστωρ", "σεβαστῶν …\nΑὐρήλιος Κάστωρ"),
    E("COMMODITY", "ὄνον", "πέπρακα τὴν\nὄνον"),
    E("PRICE_TERM", "τιμῆς", "τὸ τῆς τιμῆς"),
    E("CURRENCY", "ἀργυρίου τάλαντον", "τιμῆς\nἀργυρίου τάλαντον", "cur3"),
    E("MONEY_AMOUNT", "ἓν", "τάλαντον ἓν πλήρης", "m3"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"),
    ("c1", "m1", "HAS_PRICE"),
    ("seller", "t1", "PARTY_OF"), ("buyer", "t1", "PARTY_OF"),
]}


# ---------------------------------------------------------------------------
# Batch documents 31-50 (index 30-49). Guidelines v0.2.
# ---------------------------------------------------------------------------

SPEC["17290"] = {"entities": [  # loan acknowledgement, huge sum
    E("DATE_REF", "ὑπάτων", None, "date"),
    E("PERSON", "Διοκλητιανοῦ"), E("DATE_REF", "τὸ ε"),
    E("PERSON", "Μαξιμιανοῦ"), E("DATE_REF", "το δ"),
    E("PERSON_ROLE", "κληρονόμοις", None, "lenders"),
    E("PERSON", "Γαΐου Ἰουλίου Αὐρηλίου Διογένους"),
    E("OCCUPATION", "ὑπομνηματογράφου", "γενομένου\nὑπομνηματογράφου"),
    E("OCCUPATION", "ἐπιτρόπων"),
    E("PERSON", "Αὐρηλίων Ἰουλιανοῦ τοῦ καὶ Διοσκουρίδου"),
    E("OCCUPATION", "ὑπομνηματογράφου", "Διοσκουρίδου ὑπομνηματογράφου"),
    E("OCCUPATION", "βουλευτοῦ"),
    E("PLACE", "πόλεως τῶν Ἀλεξανδρέων"),
    E("PERSON", "Δημητριανοῦ Πλουτίωνος"),
    E("OCCUPATION", "γυμνασιαρχήσαντος"), E("OCCUPATION", "βουλευτῶν"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλεως"),
    E("PERSON", "Αὐρήλιοι Ὡριγένης Σερήνου", None, "p1"), E("PERSON", "Διοσκοροῦτος"),
    E("PERSON", "Ἁρποκρατίων", None, "p2"), E("PERSON", "Ἀνναρίης"),
    E("TRANSACTION", "ὁμολογοῦμεν", None, "t1"),
    E("CURRENCY", "ἀργυρίου Σεβαστοῦ\nνομίσματος"),
    E("CURRENCY", "δραχμῶν", "νομίσματος δραχμῶν", "cur1"),
    E("MONEY_AMOUNT", "μυριάδας τρεῖς καὶ τετρακοσίας", None, "m1"),
    E("CURRENCY", "τάλαντα", "εἰσι τάλαντα πέντε", "cur2"), E("MONEY_AMOUNT", "πέντε", None, "m2"),
    E("CURRENCY", "δραχμαὶ", "καὶ δραχμαὶ τετρακόσιαι", "cur3"), E("MONEY_AMOUNT", "τετρακόσιαι", None, "m3"),
    E("CURRENCY", "τάλαντα", "γίνονται τάλαντα ε", "cur4"), E("MONEY_AMOUNT", "ε", "τάλαντα ε", "m4"),
    E("CURRENCY", "δραχμαὶ", "τάλαντα ε δραχμαὶ υ", "cur5"), E("MONEY_AMOUNT", "υ", "δραχμαὶ υ", "m5"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"), ("m4", "cur4", "HAS_CURRENCY"),
    ("m5", "cur5", "HAS_CURRENCY"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("lenders", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["17329"] = {"entities": [  # petition over a house (heavily damaged)
    E("FRACTION", "ἡμίσους", "ἡγεμονίᾳ ἡμίσους"),  # governed noun lost to the lacuna
    E("COMMODITY", "οἶνος"), E("COMMODITY", "οἰκία"),
    E("COMMODITY", "μέρος τῆς οἰκίας"),
    E("PERSON", "Αὐρήλιος Πατερμοῦθις"),
    E("OCCUPATION", "ἄρξας βουλευτής"),
    E("DATE_REF", "ἔτους ιγ καὶ α Μεσορὴ ϛ"),
], "relations": []}

SPEC["17409"] = {"entities": [  # private letter
    E("PERSON", "Μάξιμος"), E("PERSON", "Χαιρήμονι"), E("PERSON", "Εὐδαίμονι"),
    E("DATE_REF", "τῇ ιζ"),
    E("OCCUPATION", "ἡγεμὼν"),
    E("DATE_REF", "τῇ ιϛ"),
    E("PERSON", "Τίτος Φούριος Οὐικτωρῖνος"),
    E("PERSON", "Θερμουθαρίου"),
    E("COMMODITY", "ἀμπελῶνος"),
    E("PERSON", "Σαραπίων υἱὸς Δημητρίου\nυἱοῦ Ἀπελεκήτου"),
    E("PLACE", "ῥύμην Ὠριγένους"),
    E("PERSON", "Ἡρακλείδου τοῦ\nΚαλαῆ"),
    E("DATE_REF", "ἔτους κβ"), E("DATE_REF", "Ἐπεὶφ κ"),
    E("PERSON", "Ἁροῦτος"),
    E("PLACE", "Ναρμούθει"),
    E("PERSON", "Μαξίμου", "παρὰ Μαξίμου"),
    E("OCCUPATION", "γραμματέως\nγερδίων"),
], "relations": []}

SPEC["17483"] = {"entities": [  # petition of a wife (dowry, ἕδνον)
    E("PERSON", "Φλαουίῳ Οὐαλερίῳ"), E("OCCUPATION", "ἐκδίκῳ"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλεως"),
    E("PERSON", "Αὐρηλίας Σοφίας θυγατρὸς Ἀνουθίου", None, "petitioner"),
    E("PERSON_ROLE", "τοῦ ἀνδρός μου"),
    E("PERSON_ROLE", "τοῦ ἰδίου πατρὸς"),
    E("CURRENCY", "νομίσματα", "εἰς νομίσματα\nδεκατέσσαρα", "cur1"),
    E("MONEY_AMOUNT", "δεκατέσσαρα", None, "m1"),
    E("COMMODITY", "προικῴων"),
    E("COMMODITY", "φθορίου ἕδνου"),
    E("COMMODITY", "οἰκίαν"),
    E("PERSON", "Αὐρηλία Σοφία", "κύριε.\nΑὐρηλία Σοφία"),
    E("DATE_REF", "ὑπατείας", None, "date"),
    E("PERSON", "Φλαουίου Λέοντος"),
    E("DATE_REF", "τὸ α"), E("DATE_REF", "Μεσορὴ ι"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"),
]}

SPEC["17856"] = {"entities": [  # loan/repayment of wheat
    E("DATE_REF", "ἔτους κ", "δημοσίοις.\nἔτους κ"),
    E("PERSON", "Μάρκου Αὐρηλίου Ἀντωνίνου"),
    E("PERSON", "Πουβλίου Σεπτιμίου Γέτα"),
    E("DATE_REF", "Ἁθὺρ"),
    E("PERSON", "Λούκιος Πουλφέννιος Φίλων", None, "p1"),
    E("COMMODITY", "πυροῦ", None, "c1"),
    E("UNIT", "ἀρτάβας", None, "u1"),
    E("QUANTITY", "τεσσαράκοντα\nτρεῖς", "ἀρτάβας τεσσαράκοντα\nτρεῖς", "q1"),
    E("PERSON", "Σαραπίων ὁ\nκαὶ Ὀρσ"),
    E("PERSON", "Ἱέρακος"), E("OCCUPATION", "βοηθοῦ"),
    E("UNIT", "ἄρουραι", "προκείμεναι ἄρουραι"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
]}

SPEC["18396"] = {"entities": [  # receipt for a rope for a waterwheel
    E("PLACE", "μοναστηρίου ἀββᾶ Ἀνδρέου"),
    E("PERSON", "Ἰωσῆφ"),
    E("COMMODITY", "μηχανῆς"),
    E("PLACE", "τόπου Ἠλίου"),
    E("DATE_REF", "μηνὸς Μεχεὶρ κδ ἰνδικτίωνος τετάρτης"),
    E("COMMODITY", "σχοινίον ἤτοι κρίκον", None, "c1"), E("QUANTITY", "ἕνα", None, "q1"),
    E("COMMODITY", "σχοινίον ἤτοι κρίκος", None, "c2"), E("QUANTITY", "α", "κρίκος α μόνον", "q2"),
    E("DATE_REF", "ἔτους σλβ καὶ σα Μεχεὶρ κδ ἰνδικτίωνος τετάρτης"),
    E("PERSON", "Πικῶς"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("c2", "q2", "HAS_QUANTITY"),
]}

SPEC["1842"] = {"entities": [  # Ptolemaic wage receipt (dyke labourers)
    E("DATE_REF", "ἔτους κθ Θῶυτ κε", "ἔτους κθ Θῶυτ κε.\nἔχει"),
    E("PERSON", "Νικίας", "ἔχει Νικίας εἰς τὴν"),
    E("COMMODITY", "γῆν", "τὴν\nγῆν"),
    E("OCCUPATION", "ἐργάτας", "εἰς\nἐργάτας ι", "erg1"),
    E("QUANTITY", "ι", "ἐργάτας ι ἀνὰ", "q1"),
    E("CURRENCY", "ὀβολὸν", "ἀνὰ ὀβολὸν·"),
    E("CURRENCY", "δραχμὴν", None, "cur2"), E("MONEY_AMOUNT", "α", "δραχμὴν α", "m2"),
    E("MONEY_AMOUNT", "τετρώβολον"),
    E("DATE_REF", "ἔτους κθ Θῶυτ κε"),
    E("PERSON", "Νικίας", "ἔχει Νικίας εἰς\nτὴν"),
    E("COMMODITY", "γῆν", "τὴν γῆν ἣν"),
    E("OCCUPATION", "ἐργάτας", "εἰς ἐργάτας\nι", "erg3"),
    E("QUANTITY", "ι", "ἐργάτας\nι ἀνὰ", "q3"),
    E("CURRENCY", "ὀβολὸν", "ἀνὰ ὀβολὸν· δεκόβολον"),
    E("MONEY_AMOUNT", "δεκόβολον"),
    E("DATE_REF", "Θῶυθ κε"),
    E("DATE_REF", "Θῶυτ κε", "Ἀργυρικά.\nΘῶυτ κε"),
], "relations": [
    ("m2", "cur2", "HAS_CURRENCY"),
    # 10 workers at 1 obol each (§5: HAS_QUANTITY accepts an OCCUPATION head)
    ("erg1", "q1", "HAS_QUANTITY"), ("erg3", "q3", "HAS_QUANTITY"),
]}

SPEC["18505"] = {"entities": [  # petition over a kleros (blind)
    E("DATE_REF", "ἔτους ιϛ Φαμενὼθ θ", "… ἔτους ιϛ Φαμενὼθ θ"),
    E("PERSON", "Νεάρχωι"), E("OCCUPATION", "ὑποστρατήγωι"),
    E("PLACE", "κλῆρον γειτνιῶντα"),
    E("PLACE", "Τιλῶθιν"),
    E("PLACE", "κλήρου", "ἡμῶν\nκλήρου τέταρτον"),
    E("FRACTION", "τέταρτον", "κλήρου τέταρτον"),
    E("QUANTITY", "εἴκοσι", "τὰ εἴκοσι\nσχοινία", "q1"),
    E("UNIT", "σχοινία", "εἴκοσι\nσχοινία", "u1"),
    E("DATE_REF", "η ἔτους"),
    E("COMMODITY", "πυροῦ", None, "c1"),
    E("UNIT", "ἀρτάβαι", None, "u2"), E("QUANTITY", "ε", "ἀρτάβαι ε", "q2"),
    E("DATE_REF", "ἐτῶν β", "χρόνων ἐτῶν β"),
    E("TAX_TERM", "ἐκφόρια"),
    E("PERSON", "Θέωνι"), E("OCCUPATION", "ἀρχεφόδῳ"),
    E("DATE_REF", "ἔτους ιϛ Φαμενὼθ θ", "καταντῆσαι ἔτους ιϛ Φαμενὼθ θ"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("c1", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
]}

SPEC["18620"] = {"entities": [  # cancellation of a loan
    E("PERSON", "Πρωτάρχωι"),
    E("PERSON", "Μάρκου Τιγελλίου Ἰαλύσου", None, "p1"),
    E("PERSON", "Ἔρωτος τοῦ Διοδώρου", None, "p2"),
    E("PERSON", "Καλάθου τοῦ καὶ Φιλήμονος", None, "p3"),
    E("TRANSACTION", "συνχωρεῖ", None, "t1"),
    E("PERSON", "Μᾶρκος Τιγέλλιος Ἰάλυσος"),
    E("PERSON", "Ἔρωτος", "ὑπὸ τοῦ Ἔρωτος"),
    E("PERSON", "Ἑρμίου"),
    E("PERSON", "Καλάθου", "τοῦ τοῦ Καλάθου ὀνόματος"),
    E("CURRENCY", "ἀργυρίου Πτολεμαικοῦ"),
    E("CURRENCY", "δραχμὰς", "Πτολεμαικοῦ δραχμὰς", "cur1"),
    E("MONEY_AMOUNT", "τετρακοσίας", None, "m1"),
    E("PERSON", "Καλάθωι"),
    E("PERSON", "Μᾶρκον Τιγέλλιον Ἰάλυσον"),  # second mention of the debtor
    E("PERSON", "Κάλαθον\nτὸν καὶ Φιλήμονα"),  # second mention of the creditor (alias)
    E("DATE_REF", "ἔτους κ", "ἔτους κ Καίσαρος"), E("PERSON", "Καίσαρος", "ἔτους κ Καίσαρος"),
    E("DATE_REF", "κθ", "Καίσαρος … κθ"),  # day figure, month lost to the lacuna
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("p3", "t1", "PARTY_OF"),
]}

SPEC["18621"] = {"entities": [  # cancellation of a loan, woman with guardian
    E("PERSON", "Πρωτάρχωι"),
    E("PERSON", "Τηθοήους", "παρὰ Τηθοήους", "p1"),
    E("PERSON", "Ἀλεξάνδρου τοῦ Ἀχιλλέως", None, "p2"),
    E("PERSON", "Ἀθηνίου τῆς Ἀχιλλέως", None, "p3"),
    E("PERSON_ROLE", "μετὰ κυρίου αὐτοῦ"),
    E("PERSON", "Ἀλεξάνδρου", "κυρίου αὐτοῦ Ἀλεξάνδρου"),
    E("TRANSACTION", "συνχωροῦσιν", None, "t1"),
    E("PERSON", "Ἀλέξανδρος", "συνχωροῦσιν Ἀλέξανδρος"),
    E("PERSON", "Ἀθήνιον", "καὶ Ἀθήνιον ἀπεσχηκέναι"),
    E("PERSON", "Τηθοήους", "παρὰ τοῦ Τηθοήους"),
    E("CURRENCY", "ἀργυρίου", "οἴκου\nἀργυρίου"),
    E("CURRENCY", "δραχμὰς", "ἀργυρίου δραχμὰς σμ", "cur1"),
    E("MONEY_AMOUNT", "σμ", "δραχμὰς σμ", "m1"),
    E("PERSON", "Τακονσομιν Νώχεος"),
    E("DATE_REF", "ἑβδόμῳ ἔτει", None, "date"),
    E("PERSON", "Καίσαρος"), E("DATE_REF", "Ἁθύρ"),
    # closing clause restates the three parties
    E("PERSON", "Τιθοήους", "αὐτοῦ Τιθοήους δανειστικὰς"),
    E("PERSON", "Ἀλέξανδρον", "τὸν Ἀλέξανδρον"),
    E("PERSON", "Ἀθήνιον", "καὶ Ἀθήνιον μηδʼ"),
    E("PERSON", "Τιθοῆν"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("p3", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["18699"] = {"entities": [  # request for seed-loan (blind)
    E("PERSON", "Αὐρηλίωι Ἀχιλλεῖ"), E("OCCUPATION", "στρατηγῷ"),
    E("PLACE", "Ἡρακλεοπολείτου"),
    E("PERSON", "Αὐρηλίου Πτολλᾶτος\nΝεμεσίωνος", None, "p1"),
    E("PERSON", "Ἐργέως"),
    E("PLACE", "κώμης Τεβετνυ"),
    E("TRANSACTION", "αἰτοῦμαι", None, "t1"),
    E("COMMODITY", "σπέρματα δάνεια", None, "c0"),
    E("DATE_REF", "ιβ ἔτους"),
    E("PERSON", "Μάρκου Αὐρηλίου Σεουήρου\nἈλεξάνδρου Καίσαρος"),
    E("DATE_REF", "ια ἔτους"),
    E("COMMODITY", "βασιλικὴν γῆν"),
    E("QUANTITY", "β", "ἔλαττον\nβ ἀρταβῶν", "q1"), E("UNIT", "ἀρταβῶν", None, "u1"),
    E("PLACE", "Τεβετνυ", "αὐτὴν Τεβετνυ"),
    E("PLACE", "Νικίου\nκαὶ Πτολεμαίου καὶ ἄλλων κλήρου"),
    E("UNIT", "ἀρουρῶν", None, "u2"), E("QUANTITY", "ν", "ἀρουρῶν ν", "q2"),
    E("UNIT", "ἀρτάβας", None, "u3"), E("QUANTITY", "ν", "ἀρτάβας ν", "q3"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"), ("q2", "u2", "HAS_UNIT"), ("q3", "u3", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"),
]}

SPEC["18920"] = {"entities": [  # debt acknowledgement in gold carats
    E("PERSON", "Αὐρήλιος Κόλλουθος Λιλοῦτος", None, "debtor"), E("PERSON", "Μαρίας"),
    E("OCCUPATION", "λαχανοπώλης"),
    E("PLACE", "Ἑρμουπόλεως"),
    E("PERSON", "Αὐρηλίῳ Κολλούθῳ υἱῷ Γεωργίου", None, "creditor"),
    E("OCCUPATION", "χοιρομαγείρῳ"),
    E("PLACE", "Ἀντινοέων πόλεως"),
    E("TRANSACTION", "ἔχω καὶ ὀφείλω", None, "t1"),
    E("CURRENCY", "χρυσοῦ", "ὀφείλω σοι,\nκαθαρῶς καὶ ἀποκρότως, χρυσοῦ"),
    E("CURRENCY", "κεράτια", "χρυσοῦ κεράτια ἐννέα", "cur1"),
    E("MONEY_AMOUNT", "ἐννέα", "κεράτια ἐννέα", "m1"), E("FRACTION", "ἥμισυ", "ἐννέα ἥμισυ"),
    E("CURRENCY", "χρυσοῦ κεράτια", "γίνεται χρυσοῦ κεράτια θ", "cur2"),
    E("MONEY_AMOUNT", "θ", "κεράτια θ 𐅵", "m2"), E("FRACTION", "𐅵", "θ 𐅵 ζυγῷ"),
    E("PLACE", "Ἀντινόου", "δημοσίῳ Ἀντινόου"),
    E("PLACE", "Ἀντινόου", "τῇ πόλει Ἀντινόου"),  # second mention (Antinoopolis)
    E("CURRENCY", "κερατίων", "αὐτῶν κερατίων θ", "cur3"),
    E("MONEY_AMOUNT", "θ", "κερατίων θ 𐅵·", "m3"), E("FRACTION", "𐅵", "θ 𐅵·"),
    E("CURRENCY", "χρυσοῦ νομισμάτιον", "παρέξω σοι δίχα κρίσεως καὶ δίκης χρυσοῦ νομισμάτιον", "cur4"),
    E("MONEY_AMOUNT", "ἓν", "νομισμάτιον ἓν παρὰ", "m4"),
    E("CURRENCY", "κεράτια", "παρὰ κεράτια\nἓξ", "cur5"), E("MONEY_AMOUNT", "ἓξ", "κεράτια\nἓξ", "m5"),
    E("DATE_REF", "Φαῶφι πέμπτῃ τρίτης ἰνδικτίονος"),
    E("PERSON", "Κολλούθου"), E("OCCUPATION", "λαχανοπώλου"),
    E("PLACE", "Ἑρμοῦ πόλεως"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"), ("m4", "cur4", "HAS_CURRENCY"),
    ("m5", "cur5", "HAS_CURRENCY"),
    ("debtor", "t1", "PARTY_OF"), ("creditor", "t1", "PARTY_OF"),
]}

SPEC["19306"] = {"entities": [  # house-room lease by a woman
    E("DATE_REF", "ὑπατείας", None, "date"),
    E("PERSON", "Φλαουίου Μάγνου"),
    E("DATE_REF", "Φαῶφι"),
    E("DATE_REF", "ἰνδικτίονος ιβ"),
    E("PLACE", "Ὀξυρύγχων πόλει"),
    E("PERSON", "Φλαουίῳ Ἁτρῆτι", None, "lessor"),
    E("PERSON", "Μαρτυρίου"),
    E("PLACE", "Ὀξυρυγχιτῶν πόλει"),
    E("PERSON", "Αὐρηλία Νόννα\nθυγάτηρ Ἀπολλω", None, "lessee"), E("PERSON", "Ἄννας"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("DATE_REF", "μηνὸς Θὼθ"),
    # Oxyrhynchite double era-year (195 = 164): one date expression, two figures.
    E("DATE_REF", "ἔτους ρϙε ρξδ"),
    E("DATE_REF", "δωδεκάτης ἰνδικτίονος"),
    E("PLACE", "ἀμφόδου Δρόμου Σαραπίου"),
    E("COMMODITY", "οἰκίας"),
    E("COMMODITY", "ἐξέδραν"),
    E("TAX_TERM", "ἐνοικίου"),
    E("CURRENCY", "χρυσοῦ νομισματίου", "ἐνιαυσίως χρυσοῦ νομισματίου"),
    E("FRACTION", "δίμοιρον"),
    E("CURRENCY", "χρυσοῦ", "γίνεται χρυσοῦ νομιτευόμενον"),
    E("CURRENCY", "νομισματίου", "νομιτευόμενον\nνομισματίου 𐅷", "cur1"),
    E("FRACTION", "𐅷", None, "fr1"),
    E("PERSON", "Αὐρηλία Νόννα θυγάτηρ Ἀπολλω", "ὡμολόγησα.\nΑὐρηλία Νόννα θυγάτηρ Ἀπολλω"),
    E("FRACTION", "ἥμισυ", "ἐνιαυσίως\nἥμισυ"),
    E("PERSON", "Αὐρηλίας Νόννας", "μίσθωσις Αὐρηλίας Νόννας"),
], "relations": [
    ("fr1", "cur1", "HAS_CURRENCY"),
    ("lessor", "t1", "PARTY_OF"), ("lessee", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["2001"] = {"entities": [
    # A 132-char scrap of a petition: no legible economic content, and δεόμεθα
    # ("we ask") is a request, not a transfer. A true-negative document.
], "relations": []}

SPEC["20069"] = {"entities": [  # land lease
    E("PERSON", "Αὐρηλίᾳ Διογενίδι τῇ καὶ Ἡρακλείᾳ", None, "lessor"),
    E("PERSON_ROLE", "ματρώνᾳ στολάτᾳ"),
    E("PERSON", "Ἁρποκρατίωνος"), E("OCCUPATION", "προνοητοῦ"),
    E("PERSON", "Αὐρηλίων Πεθώτου Παήσιος", None, "p1"), E("PERSON", "Τασουκᾶτος"),
    E("PERSON", "Ἁρπαθώτου Σαρᾶτος", None, "p2"), E("PERSON", "Εὖτος"),
    E("PLACE", "κώμης Μαγδώλων Μίρη"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("PERSON", "Γαλλιηνοῦ Σεβαστοῦ"),
    E("PLACE", "Ποαμπινοῦφιν"),
    E("PLACE", "Ἀγαζήλου κλήρου"),
    E("UNIT", "ἀρούρας", "κλήρου\nἀρούρας δέκα ὀκτὼ", "u1"),
    E("QUANTITY", "δέκα ὀκτὼ", None, "q1"),
    E("COMMODITY", "πυροῦ"), E("COMMODITY", "χόρτου"),
    E("FRACTION", "ἥμισυ", "κατὰ τὸ ἥμισυ"),
    E("TAX_TERM", "φόρου"),
    E("UNIT", "ἀρτάβας", None, "u2"), E("QUANTITY", "τέσσαρας", None, "q2"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"), ("q2", "u2", "HAS_UNIT"),
    ("lessor", "t1", "PARTY_OF"), ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"),
]}

SPEC["20335"] = {"entities": [  # loan of wheat, repayment in kind (blind)
    E("PERSON", "Αὐρήλιοι Πεκῦσις Παυσείριος", None, "p1"), E("PERSON", "Σοήριος"),
    E("PERSON", "Πετενοῦφις", "υἱὸς Πετενοῦφις", "p2"), E("PERSON", "Σινθεῦτος"),
    E("PLACE", "Ὀξυρύγχων πόλεως"),
    E("PERSON", "Αὐρηλίῳ\nΘέωνι Διδύμου", None, "p3"),
    E("TRANSACTION", "ὁμολογοῦμεν", None, "t1"),
    E("COMMODITY", "πυροῦ", "παραμεμετρῆσθαι παρὰ σοῦ πυροῦ", "c1"),
    E("DATE_REF", "δ ἔτους"),
    E("UNIT", "ἀρτάβας", "ἔτους ἀρτάβας\nτέσσαρας", "u1"), E("QUANTITY", "τέσσαρας", None, "q1"),
    E("COMMODITY", "πυροῦ", "αὐτὸ πυροῦ σὺν", "c2"),
    E("UNIT", "ἀρτάβας", "διαφόρῳ ἀρτάβας ἕξ", "u2"), E("QUANTITY", "ἕξ", "ἀρτάβας ἕξ", "q2"),
    E("DATE_REF", "Παῦνι\nμηνὶ"),
    E("PLACE", "κώμης Τερύθεως"),
    E("COMMODITY", "πυρὸν νέον καθαρὸν ἄδολον"),
    E("DATE_REF", "ἔτους ε", None, "date"),
    # full imperial titulature is one PERSON span (Severus Alexander)
    E("PERSON", "Αὐτοκράτορος Καίσαρος\nΜάρκου Αὐρηλίου Σεουήρου Ἀλεξάνδρου\nΕὐσεβοῦς Εὐτυχοῦς Σεβαστοῦ"),
    E("DATE_REF", "Ἁθὺρ η"),
    E("PERSON", "Αὐρήλιοι Πεκῦσις\nΠαυσείριος", "Ἁθὺρ η. Αὐρήλιοι Πεκῦσις\nΠαυσείριος"),
    E("PERSON", "Πετενοῦφις", "υἱὸς Πετενοῦφις παραμεμετρήμεθα"),
    E("PERSON", "Αὐρηλίου Θέωνος"),
    E("COMMODITY", "πυροῦ", "τὰς τοῦ πυροῦ ἀρτάβας"),
    E("UNIT", "ἀρτάβας", "τοῦ πυροῦ ἀρτάβας\nτέσσαρας"),
    # subscription docket: Pekysis, 4 artabas (of wheat)
    E("PERSON", "Αὐρήλιος Πετρώνιος\nΜάρκου"),
    E("PERSON", "Πεκύσιος", "χειρόγραφον Πεκύσιος"),
    E("UNIT", "ἀρταβῶν", None, "ud"), E("QUANTITY", "δ", "ἀρταβῶν δ", "qd"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("qd", "ud", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("p3", "t1", "PARTY_OF"),
    ("t1", "date", "DATED_TO"),
]}

SPEC["20799"] = {"entities": [  # official letter, land registration
    E("DATE_REF", "ιη", "ιη τῷ ἐνεστῶτι"),  # day figure opening the fragment
    E("DATE_REF", "μηνὶ Φαῶφι", "ἐνεστῶτι\nμηνὶ Φαῶφι"),
    E("PLACE", "Σύρων κώμην"),
    E("PLACE", "Φιλίππου\nσὺν τῷ Ἀνθι… κλήρου"),
    E("UNIT", "ἀρούρας", None, "u1"), E("QUANTITY", "τέσσαρας", None, "q1"),
    E("DATE_REF", "ἔτους τρίτου", None, "date"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος\nΝέρουα Τραιανοῦ\nΣεβαστοῦ Γερμανικοῦ"),
    E("DATE_REF", "Φαῶφι ιε"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
]}

SPEC["20815"] = {"entities": [  # sale of a prophetship (office), damaged
    E("PERSON", "Μάρκιος Μοισιακὸς"), E("OCCUPATION", "στρατηγῷ"),
    E("PLACE", "Ἑρμοπολίτου"),
    E("PERSON", "Ἁρθώτου Ἁρθώτου", None, "buyer"),
    E("DATE_REF", "τῇ ι"),
    E("COMMODITY", "προφητείαν", None, "c1"),
    E("CURRENCY", "ταλάντου", "τάξεις ταλάντου α", "cur1"), E("MONEY_AMOUNT", "α", "ταλάντου α\n", "m1"),
    E("PERSON", "Σεκούνδῳ"), E("OCCUPATION", "οἰκονόμῳ"),
    E("CURRENCY", "δραχμὰς", "οἰκονόμῳ δραχμὰς φ", "cur2"), E("MONEY_AMOUNT", "φ", "δραχμὰς φ", "m2"),
    # prepayment of 1500 (drachmas elided, same denomination as δραχμὰς φ above)
    E("MONEY_AMOUNT", "Αφ", "προαποδεδωκέναι Αφ"),
    E("PRICE_TERM", "τιμῆς"),
    E("DATE_REF", "ἔτους ζ", None, "date"),
    E("PERSON", "Ἁδριανοῦ Καίσαρος"),
    E("DATE_REF", "Μεχεὶραεχ ιε", "χυ Μεχεὶραεχ ιε"),
    E("PERSON", "Ἁρθώτῃ Ἁρθώτου"),
    E("COMMODITY", "προφητείας", "Ἁρθώτου προφητείας"),
    E("CURRENCY", "ταλάντου", "ἀπὸ ταλάντου α", "cur3"), E("MONEY_AMOUNT", "α", "ταλάντου α\n", "m3"),
    E("DATE_REF", "τῇ κ Μεσορὴ τοῦ ε ἔτους"),
    E("MONEY_AMOUNT", "Αφ", "ε ἔτους Αφ"),
    E("DATE_REF", "ϛ ἔτει"),
    E("PLACE", "Μαρσισούχῳ"),
    E("PLACE", "Πακήβκεως"),
    E("MONEY_AMOUNT", "Αφ", "ἄλλας Αφ"),
    E("MONEY_AMOUNT", "Γ", "τὰς λοιπὰς Γ"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("m3", "cur3", "HAS_CURRENCY"),
    ("c1", "m1", "HAS_PRICE"),
]}

SPEC["20820"] = {"entities": [  # slave-sale fragment (blind)
    E("PLACE", "κατοίκων"),
    E("PERSON", "Πατῦνις Ὥρου"),
    E("UNIT", "ἀρτάβη", None, "u1"), E("QUANTITY", "α", "ἀρτάβη α", "q1"),
    E("TRANSACTION", "πρᾶσις", "ἀντίγραφον· πρᾶσις", "t1"),
    E("PERSON", "Παροδίωνος", None, "slave"), E("PERSON_ROLE", "δούλου", "Παροδίωνος δούλου"),
    E("DATE_REF", "ἔτους", "κα… ἔτους …", "date"),
    E("PERSON", "Τιβερίου Καίσαρος Σεβαστοῦ"),
    E("DATE_REF", "μηνὸς Νέου Σεβαστοῦ β"),
    E("PERSON_ROLE", "δούλου", "ἀποστασίου δούλου"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("slave", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO"),
]}

SPEC["20983"] = {"entities": [  # petition to dissolve a will
    E("PERSON", "Ἰσιδώρῳ"), E("OCCUPATION", "στρατηγῷ"),
    E("PERSON", "Θέωνος Παυσειρίωνος τοῦ\nκαὶ Γερμανίου Ἰσᾶτος", None, "petitioner"),
    E("PERSON", "Ταυσαράπιος τῆς καὶ Σεραοῦτος"),
    E("PLACE", "Ὀξυρύγχων πόλεως"),
    E("PERSON_ROLE", "ἀπελευθέρα"),
    E("PERSON", "Σαραπίωνος Ἀπολλωνίου"),
    E("PERSON", "Ἡρακλοῦτος"),
    E("DATE_REF", "μηνὶ Γερμανικείου"),
    E("DATE_REF", "τρισκαιδεκάτου ἔτους"),
    E("PERSON", "Αὐρηλίου\nἈντωνίνου Καίσαρος"),
    E("PERSON", "Διονύσιον τὸν καὶ Ἀμόιν Ἡρακλείδου τοῦ Διονυσίου τοῦ καὶ Ἀμόι"),
    E("PERSON", "Σαραποῦτος"),
    E("PERSON", "Διογένην Ἀπολλοφάνους τοῦ\nΔιογένους"),
    E("PERSON", "Σαραπίωνα Χαιρήμονος τοῦ Σωσιβίου"),
    E("PERSON", "Ἀγαθὸν Δαίμονα"),
    E("PERSON_ROLE", "ἀπελεύθερον"),
    E("PERSON", "Ἡρακλείδου καὶ Σαραπίωνος τοῦ καὶ Δωρίωνος"),
    E("PERSON", "Ὥρῳ τῷ καὶ Ὡρίωνι"),
    E("PERSON", "Δημητρίῳ", "καὶ\nΔημητρίῳ"),
    E("CURRENCY", "δραχμὰς", "δίδοσθαι λύσεως διαθήκης δραχμὰς δέκα δύο", "cur1"),
    E("MONEY_AMOUNT", "δέκα δύο", None, "m1"),
    E("DATE_REF", "ἔτους ιδ", None, "date"),
    E("PERSON", "Μάρκου Αὐρηλίου\nἈντωνίνου Σεβαστοῦ"),
    E("DATE_REF", "Παῦνι ιη ιδ"),
    E("PERSON", "Θέων Παυσιρίωνος"),
    E("DATE_REF", "Παῦνι ιη", "ἐπιδέδωκα.\nΠαῦνι ιη"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"),
]}

# ============================ batch 2: docs 51-100 ==========================

SPEC["21035"] = {"entities": [  # loan repayment via a bank diagraphe
    E("PERSON", "Ἀπολλωφανοῦς\nτοῦ Πτολεμαίου"),
    E("DATE_REF", "ἔτους δ", None, "date"),
    E("PERSON", "Νέρωνος Κλαυδίου Καίσαρος Σεβαστοῦ Γερμανικοῦ\nΑὐτοκράτορος"),
    E("DATE_REF", "μηνὸς Σεβαστοῦ\nκδ"),
    E("PERSON", "Λούκιος Οὐέττιος Λουκίου υἱὸς\nΔιογένης", None, "lender"),
    E("OCCUPATION", "ἱππέων", "ἀπολελυμένων\nἱππέων"),
    E("PERSON", "Μάρκωι Ἀντωνίωι\nΔιονυσίωι", None, "borrower"),
    E("OCCUPATION", "ἱππεῖ", "Διονυσίωι ἱππεῖ"),
    E("PERSON", "Φρόντωνος"),
    E("TRANSACTION", "ἐδανείσατο", None, "t1"),
    E("CURRENCY", "ἀργυρίου", "τραπέζης ἀργυρίου δραχμὰς Ασ"),
    E("CURRENCY", "δραχμὰς", "ἀργυρίου δραχμὰς Ασ", "dr1"), E("MONEY_AMOUNT", "Ασ", "δραχμὰς Ασ", "m1"),
    E("CURRENCY", "ἀργυρίου", "χειρὸς ἀργυρίου δραχμὰς ψ"),
    E("CURRENCY", "δραχμὰς", "ἀργυρίου δραχμὰς ψ", "dr2"), E("MONEY_AMOUNT", "ψ", "δραχμὰς ψ", "m2"),
    E("CURRENCY", "ἀργυρίου", "ἀργυρίου δραχμὰς φ"),
    E("CURRENCY", "δραχμὰς", "ἀργυρίου δραχμὰς φ", "dr3"), E("MONEY_AMOUNT", "φ", "δραχμὰς φ", "m3"),
], "relations": [
    ("m1", "dr1", "HAS_CURRENCY"), ("m2", "dr2", "HAS_CURRENCY"), ("m3", "dr3", "HAS_CURRENCY"),
    ("lender", "t1", "PARTY_OF"), ("borrower", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO"),
]}

SPEC["21224"] = {"entities": [  # loan of 2 gold solidi (Byzantine)
    E("DATE_REF", "ὑπατείαν", None, "date"),
    E("PERSON", "Ὁννωρίου"), E("DATE_REF", "τὸ ιγ"),
    E("PERSON", "Θεοδοσίου"), E("DATE_REF", "τὸ ι", "Θεοδοσίου τὸ ι"),
    E("DATE_REF", "Ἐπεὶφ λ"),
    E("DATE_REF", "ἑβδόμης\nἰνδικτίωνος"),
    E("PERSON", "Αὐρήλιος Λούκιος Ἑρμῆτος", "ἰνδικτίωνος. Αὐρήλιος Λούκιος Ἑρμῆτος", "borrower"),
    E("PERSON", "Ἀρωνᾶς"),
    E("PLACE", "κώμης Τερύθεως"),
    E("PLACE", "Ἄνω Κυνοπολείτου νομοῦ"),
    E("PERSON", "Αὐρηλίῳ\nΠασαλυμίῳ Παπνουθίου", None, "creditor"),
    E("OCCUPATION", "μονάζοντι"),
    E("TRANSACTION", "ὁμολογῶ", "χαίρειν. ὁμολογῶ", "t1"),
    E("CURRENCY", "χρυσοῦ", "χρείαν χρυσοῦ δόκιμα"),
    E("CURRENCY", "νομισμάτια", "εὔσταθμα νομισμάτια δύο", "cur1"),
    E("MONEY_AMOUNT", "δύο", "νομισμάτια δύο", "m1"),
    E("CURRENCY", "χρυσοῦ", "γίνεται χρυσοῦ νομισμάτια β"),
    E("CURRENCY", "νομισμάτια", "γίνεται χρυσοῦ νομισμάτια β", "cur2"),
    E("MONEY_AMOUNT", "β", "νομισμάτια β,", "m2"),
    E("CURRENCY", "χρυσοῦ νομισμάτιον", "ἄλλον χρυσοῦ νομισμάτιον ἓν", "cur3"),
    E("MONEY_AMOUNT", "ἓν", "νομισμάτιον ἓν δώσω", "m3"),
    E("CURRENCY", "ἀργυρίου", "ἐνιαυτὸν ἀργυρίου"),
    E("CURRENCY", "μυριάδας", None, "cur4"),
    E("MONEY_AMOUNT", "τετρακοσίας ὀγδοήκοντα", None, "m4"),
    E("PERSON", "Αὐρήλιος Λούκιος\nἙρμῆτος", "ὡμολόγησα. Αὐρήλιος Λούκιος\nἙρμῆτος"),
    E("CURRENCY", "χρυσοῦ", "τὰ τοῦ χρυσοῦ νομισμάτια δύο"),
    E("CURRENCY", "νομισμάτια", "τοῦ χρυσοῦ νομισμάτια δύο", "cur5"),
    E("MONEY_AMOUNT", "δύο", "χρυσοῦ νομισμάτια δύο", "m5"),
    E("PERSON", "Αὐρήλιος Φλαυιανὸς\nἨλίου"),
    E("PLACE", "κώμης Θμοινπέλλα"),
    E("PERSON", "Λουκίου Ἑρμῆτος", "χειρόγραφον Λουκίου Ἑρμῆτος"),
    E("CURRENCY", "χρυσοῦ", "Ἑρμῆτος χρυσοῦ νομισμάτια β"),
    E("CURRENCY", "νομισμάτια", "χρυσοῦ νομισμάτια β.", "cur6"),
    E("MONEY_AMOUNT", "β", "νομισμάτια β.", "m6"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"), ("m3", "cur3", "HAS_CURRENCY"),
    ("m4", "cur4", "HAS_CURRENCY"), ("m5", "cur5", "HAS_CURRENCY"), ("m6", "cur6", "HAS_CURRENCY"),
    ("borrower", "t1", "PARTY_OF"), ("creditor", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO"),
]}

SPEC["21250"] = {"entities": [  # sale/cession of a tax liability (Arab-era, damaged)
    E("PERSON", "Φλαυίου\nἩρακλείου τοῦ αἰωνίου Αὐγούστου καὶ Αὐτοκράτορος"),
    E("DATE_REF", "ἔτους ἐνάτου"), E("DATE_REF", "Ἐπεὶφ δωδεκάτῃ"),
    E("DATE_REF", "ἑβδόμης ἰνδικτίονος"),
    E("PLACE", "Ἑρμουπόλει"), E("PLACE", "Θηβαίδος"),
    E("TAX_TERM", "δημοσίῳ", "τῷ δημοσίῳ λόγῳ"),
    E("PLACE", "πόλεως Ἑρμουπολιτῶν"),
    E("PERSON", "Φλαυίου Μαγίστορος υἱοῦ Καλλινίκου"),
    E("OCCUPATION", "βοηθοῦ τοῦ λογιστηρίου"), E("OCCUPATION", "διαστολέως"),
    E("PLACE", "μερίδος Διοσκορίδου", "καὶ διαστολέως\n… μερίδος Διοσκορίδου"),
    E("PERSON", "Αὐρήλιος Ἐνῶχ υἱὸς Πκαλίου", None, "party1"),
    E("OCCUPATION", "γεωργὸς"),
    E("TRANSACTION", "θελήσῃ", "χαίρειν. θελήσῃ", "t1"),
    E("PERSON", "Θεοφίλῃ", None, "party2"), E("PERSON", "Βίκτορος", "θυγατρὶ Βίκτορος"),
    E("TAX_TERM", "δημοσίων", "τρακτευομένων παρὰ σοῦ δημοσίων"),
    E("COMMODITY", "σίτου", "σίτου καθαροῦ"),
    E("UNIT", "ἀρτάβης", None, "u1"),
    E("QUANTITY", "μιᾶς", "μιᾶς ἡμίσους", "q1"),
    E("FRACTION", "ἡμίσους", "μιᾶς ἡμίσους"), E("FRACTION", "τετάρτου", "ἡμίσους τετάρτου"),
    E("CURRENCY", "χρυσοῦ", "καὶ χρυσοῦ κερατίων δέκα"),
    E("CURRENCY", "κερατίων", "χρυσοῦ κερατίων δέκα", "cur1"),
    E("MONEY_AMOUNT", "δέκα", "κερατίων δέκα", "m1"),
    E("PERSON", "Κοπρέους"),
    E("PERSON", "Θεοφίλης", "παρὰ τῆς Θεοφίλης"),  # recap of the counterparty
    E("UNIT", "ἀρούρης", None, "u2"), E("FRACTION", "τετάρτου", "ἀρούρης τετάρτου"),
    E("COMMODITY", "γῆς", "ἀνύδρου γῆς"),
    E("PLACE", "κώμης Θύνεως"),
    E("PLACE", "μερίδος Διοσκορίδου", "αὐτῆς μερίδος Διοσκορίδου"),  # recap
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("m1", "cur1", "HAS_CURRENCY"),
    ("party1", "t1", "PARTY_OF"), ("party2", "t1", "PARTY_OF"),
]}

SPEC["21630"] = {"entities": [  # receipt from the hospital of Leukadios (blind)
    E("DATE_REF", "Θὼθ κα", None, "date"), E("DATE_REF", "ἰνδικτίωνος\nτετάρτης"),
    E("PERSON", "Φλαουΐῳ Ἀπίωνι", None, "payer"), E("OCCUPATION", "ὑπάτῳ"),
    E("PLACE", "Ὀξυρυγχιτῶν\nπόλει"),
    E("PERSON", "Μηνᾶ"), E("OCCUPATION", "οἰκέτου"),
    E("PLACE", "νοσοκομεῖον τὸ καλούμενον\nΛευκαδίου"),
    E("PERSON", "Μαύρας", "ἐμοῦ Μαύρας"), E("OCCUPATION", "οἰκονόμου", "αὐτῷ οἰκονόμου"),
    E("TRANSACTION", "ἔσχον", "ἔσχον ἐγὼ", "t1"),
    E("PERSON", "Μαύρα", "αὐτὴ\nΜαύρα", "recv"),
    E("DATE_REF", "τετάρτης ἰνδικτίωνος", "παρούσης\nτετάρτης ἰνδικτίωνος"),
    E("COMMODITY", "σίτου", "προσάπαξ\nσίτου ἀρτάβας ἑπτά", "c1"),
    E("UNIT", "ἀρτάβας", None, "u1"), E("QUANTITY", "ἑπτά", "ἀρτάβας ἑπτά", "q1"),
    E("COMMODITY", "σίτου", "γίνονται σίτου\nἀρτάβαι ζ", "c2"),
    E("UNIT", "ἀρτάβαι", "σίτου\nἀρτάβαι ζ", "u2"), E("QUANTITY", "ζ", "ἀρτάβαι ζ,", "q2"),
    E("PERSON", "Ἀνοῦπ"), E("OCCUPATION", "νοταρίου"),
    E("PERSON", "Μαύρα", "ἐγὼ Μαύρα οἰκονόμος"), E("OCCUPATION", "οἰκονόμος"),
    E("PLACE", "νοσοκομείου Λευκαδίου", "τοῦ νοσοκομείου Λευκαδίου\nστοιχεῖ"),
    E("PERSON", "Ἰωσὴφ"),
    E("PLACE", "νοσοκομείου καλουμένου Λευκαδίου"),
    E("PERSON", "Μαύρας", "διὰ Μαύρας οἰκονόμου"), E("OCCUPATION", "οἰκονόμου", "Μαύρας οἰκονόμου"),
    E("COMMODITY", "σίτου", "οἰκονόμου\nσίτου ἀρτάβαι ζ", "c3"),
    E("UNIT", "ἀρτάβαι", "σίτου ἀρτάβαι ζ.", "u3"), E("QUANTITY", "ζ", "ἀρτάβαι ζ.", "q3"),
], "relations": [
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("c3", "q3", "HAS_QUANTITY"), ("q3", "u3", "HAS_UNIT"),
    ("t1", "date", "DATED_TO"),
    ("payer", "t1", "PARTY_OF"), ("recv", "t1", "PARTY_OF"),
]}

SPEC["21700"] = {"entities": [  # private letter about selling barley (blind)
    E("PERSON", "Γλουτᾶς"), E("PERSON", "Εὐτυχίδῃ"), E("OCCUPATION", "γυμνασιάρχῳ"),
    E("COMMODITY", "κριθήν"),
    E("QUANTITY", "ιε", "τῶν ιε ἀρταβῶν", "q1"), E("UNIT", "ἀρταβῶν", "ιε ἀρταβῶν", "u1"),
    E("PERSON", "Θαήσιος"),
    E("DATE_REF", "ἔτους γ", None, "date"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος\nΟὐασπασιανοῦουασπασιηνου"),  # name doubled in source
    E("DATE_REF", "Χοίακ ιδ"),
    E("PERSON", "Ἐπήμαχον"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
]}

SPEC["22572"] = {"entities": [  # lease of 20 arouras for hay
    E("DATE_REF", "ὑπατείας"),
    E("PERSON", "Φλαουίων Ἀρβετίωνος"), E("PERSON", "Λολλιανοῦ"),
    E("DATE_REF", "Φαῶφι γ"),
    E("PERSON", "Φλαουίῳ Ἰουλιανῷ", None, "owner1"), E("OCCUPATION", "λογιστῶν"),
    E("PERSON", "Σαραπιάδι", None, "owner2"), E("PERSON", "Διοσκουρίδου"),
    E("FRACTION", "ἥμισυ", "ἑκάστῳ ἥμισυ μέρος"),
    E("PLACE", "Ὀξυρυγχίτῃ"),
    E("PERSON", "Αὐρηλίου Πατερέως Χωοῦος", None, "lessee"),
    E("PLACE", "κώμης Ἰσίου Παγγᾶ"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("DATE_REF", "ἔτος λβ"),
    E("PLACE", "ἐποικίου\nΠατβώνθεως"),
    E("UNIT", "ἀρούρας", "ἀρούρας εἴκοσι", "u1"), E("QUANTITY", "εἴκοσι", "ἀρούρας εἴκοσι", "q1"),
    E("COMMODITY", "χόρτου"),
    E("TAX_TERM", "φόρου"),
    E("PERSON", "Πατερέως", "μίσθωσις Πατερέως"),
    E("PLACE", "Ἰσίου Παγγᾶ", "ἀπὸ Ἰσίου Παγγᾶ"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("owner1", "t1", "PARTY_OF"), ("owner2", "t1", "PARTY_OF"), ("lessee", "t1", "PARTY_OF"),
], "skips": [S("α", "non_referential", "τοῦ α πάγου")]}

SPEC["22840"] = {"entities": [  # order to a sitologos to measure out 4 artabas of wheat
    E("PERSON", "Διόδοτος Νωρβάνας Κλάρας", None, "orderer"),
    E("PERSON", "Γαίου Ἰουλίου Σαλουίου"),
    E("PERSON", "Μητόκωι", None, "sitologos"), E("OCCUPATION", "σιτολόγωι"),
    E("TRANSACTION", "μέτρησον", None, "t1"),
    E("DATE_REF", "μηνὸς Φαρμοῦθι"), E("DATE_REF", "Παχὼν"), E("DATE_REF", "Παῦνι"),
    E("DATE_REF", "Ἐπεὶφ", "καὶ Ἐπεὶφ μηνῶν"),
    E("UNIT", "μηνῶν", None, "um"), E("QUANTITY", "δ", "μηνῶν δ", "qm"),
    E("DATE_REF", "ια ἔτους"),
    E("COMMODITY", "πυροῦ", "ἔτους πυροῦ ἀρτάβας", "c1"),
    E("UNIT", "ἀρτάβας", "πυροῦ ἀρτάβας τέσσαρες", "u1"), E("QUANTITY", "τέσσαρες", "ἀρτάβας τέσσαρες", "q1"),
    E("DATE_REF", "ἔτους ιβ"),
    E("PERSON", "Νέρωνος Κλαυδίου Καίσαρος Σεβαστοῦ\nΓερμανικοῦ Αὐτοκράτορος"),
    E("DATE_REF", "Τῦβι ι"),
    E("PERSON", "Γάιος Ἰούλιος Σάλουιος"),
    E("COMMODITY", "πυροῦ", "τὰς τοῦ\nπυροῦ ἀρτάβας", "c2"),
    E("UNIT", "ἀρτάβας", "πυροῦ ἀρτάβας τέσσαρες γίνονται", "u2"), E("QUANTITY", "τέσσαρες", "ἀρτάβας τέσσαρες γίνονται", "q2"),
    E("COMMODITY", "πυροῦ", "γίνονται πυροῦ ἀρτάβαι δ", "c3"),
    E("UNIT", "ἀρτάβαι", "πυροῦ ἀρτάβαι δ", "u3"), E("QUANTITY", "δ", "ἀρτάβαι δ", "q3"),
], "relations": [
    ("qm", "um", "HAS_UNIT"),
    ("c1", "q1", "HAS_QUANTITY"), ("q1", "u1", "HAS_UNIT"),
    ("c2", "q2", "HAS_QUANTITY"), ("q2", "u2", "HAS_UNIT"),
    ("c3", "q3", "HAS_QUANTITY"), ("q3", "u3", "HAS_UNIT"),
    ("orderer", "t1", "PARTY_OF"), ("sitologos", "t1", "PARTY_OF"),
]}

SPEC["22922"] = {"entities": [  # cession of half an undertaker's business
    E("PERSON", "Ψεννῆσις Ὥρου υἱοῦ Σεναμούνιος", None, "seller"), E("PERSON", "Κλαυδίας"),
    E("OCCUPATION", "νεκροτάϕος"), E("PLACE", "Κύσεως", "ἀπὸ Κύσεως"),
    E("PERSON", "Πολυδεύκῃ ἐπικεκλημένῳ Μέρσι", None, "buyer"),
    E("PERSON_ROLE", "ἀπελευθέρῳ"),
    E("PERSON", "Πετεχῶντος", "ἀπελευθέρῳ Πετεχῶντος"),
    E("PERSON", "Πετοσίριος"), E("PERSON", "Πετεχῶντος", "ἀμφοτέρων Πετεχῶντος"),
    E("OCCUPATION", "νεκροτάφῳ", "Πετεχῶντος νεκροτάφῳ"), E("PLACE", "Ἵβεως"),
    E("TRANSACTION", "ὁμολογῶ", "χαίρειν. ὁμολογῶ", "t1"),
    E("FRACTION", "ἥμισυ", "μέρος ἥμισυ"),
    E("COMMODITY", "ὑπηρεσίας καὶ κηδείας νεκροταφικῆς", None, "c1"),
    E("PLACE", "κώμῃ Πμουνήσει"), E("PLACE", "Κύσεως", "Πμουνήσει τῆς Κύσεως"),
    E("PERSON", "Ὥρου", "κληρονομίας Ὥρου πατρός"),
    E("PRICE_TERM", "τιμῆς"),
    E("CURRENCY", "ἀργυρίου", "χειρὸς ἐκ πλήρους ἀργυρίου"),
    E("CURRENCY", "δραχμῶν", "ἀργυρίου δραχμῶν τριακοσίων", "cur1"),
    E("MONEY_AMOUNT", "τριακοσίων", None, "m1"),
    E("CURRENCY", "δραχμαὶ", "γίνονται δραχμαὶ τ", "cur2"), E("MONEY_AMOUNT", "τ", "δραχμαὶ τ.", "m2"),
    E("DATE_REF", "ἔτους α"),
    E("PERSON", "Αὐτοκράτορος Καίσαρος Μάρκου Ἰουλίου Φιλίππου Εὐσεβοῦς Εὐτυχοῦς\nΣεβαστοῦ"),
    E("DATE_REF", "Ἐπειφ δ"),
    E("PERSON", "Αὐρήλιος Ψεναμοῦνις ὁ καὶ Ἄμμων"),
    E("PERSON", "Ψεννῆσις Ὥρου", "Ψεννῆσις Ὥρου ὁ προκείμενος"), E("PRICE_TERM", "τιμὴν"),
    E("PERSON", "Αὐρήλιος Βασιλείδης ὁ καὶ Σαραπιόδωρος"),
    E("PERSON", "Αὐρήλιος Ἀπίων Σαραπίωνος"),
    E("PERSON", "Αὐρήλιος Διονυσίδης"),
], "relations": [
    ("m1", "cur1", "HAS_CURRENCY"), ("m2", "cur2", "HAS_CURRENCY"),
    ("c1", "m1", "HAS_PRICE"),
    ("seller", "t1", "PARTY_OF"), ("buyer", "t1", "PARTY_OF"),
]}

SPEC["23019"] = {"entities": [  # lease of state land under oath (damaged)
    E("PERSON", "Φιλώτου", None, "lessee1"),
    E("OCCUPATION", "γεωργῶν", "δημοσίων γεωργῶν"),
    E("PERSON", "Καίσαρα\nΑὐτοκράτορα θεοῦ υἱὸν Δία Ἐλευθέριον\nΣεβαστὸν"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("PERSON", "Δημήτριος", None, "lessee2"),
    E("PLACE", "Ὀξυρυγχείτου νομοῦ"),
    E("DATE_REF", "πεντεκαιδέκατον ἔτος"),
    E("PERSON", "Καίσαρος", "ἔτος Καίσαρος"),
    E("PERSON", "Ἡρακλείδου τοῦ Τληπολέμου"),
    E("UNIT", "ἀρούρας", "ἀρούρας δύο", "u1"), E("QUANTITY", "δύο", "ἀρούρας δύο", "q1"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"),
    ("lessee1", "t1", "PARTY_OF"), ("lessee2", "t1", "PARTY_OF"),
]}

SPEC["23580"] = {"entities": [  # account of house/room rents (damaged)
    E("PERSON", "Κλαυδίαι"),
    E("PERSON", "Κλαυδίου Συρίωνος"), E("OCCUPATION", "γυμνασιάρχου"),
    E("PLACE", "Ἀλεξανδρέων"),
    E("PERSON", "Κλαυδίου", "διὰ Κλαυδίου Ι"),
    E("PERSON", "Αὐρηλίων Διονυσίου"),
    E("PLACE", "Μεμφειτῶν πόλεως"),
    E("OCCUPATION", "προνοητῶν"),
    E("DATE_REF", "ε ἔτους"),
    E("PERSON", "Αὐτοκράτορος Μάρκου Ἀντωνίου Γορδιανοῦ\nΕὐσεβοῦς Εὐτυχοῦς Σεβαστοῦ"),
    E("TAX_TERM", "φόρου"),
    E("TAX_TERM", "ἐνοικίου", "πενταετοῦς ἐνοικίου"), E("COMMODITY", "οἰκίας", "παλαιᾶς οἰκίας"),
    E("TAX_TERM", "ἐνοικίου", "ἐνοικίου κέλλης ἀπὸ βορρᾶ"), E("COMMODITY", "κέλλης", "ἐνοικίου κέλλης ἀπὸ βορρᾶ"),
    E("PERSON", "Μασυλλᾶ"),
    E("COMMODITY", "κέλλης", "ἄλλης κέλλης ἀπὸ νότου"),
    E("PERSON", "Εὐδαίμονος"), E("OCCUPATION", "οἰνοπράτου"),
    E("PERSON", "Σερήνου"), E("OCCUPATION", "μισθωτοῦ"),
    E("TAX_TERM", "ἐνοικίου", "ἐνοικίου ἡλιαστηρίου"), E("COMMODITY", "ἡλιαστηρίου"),
    E("PLACE", "Μέμφει"),
    E("PERSON", "Εἰρηνίωνος Πάειτος"),
], "relations": []}

SPEC["22127"] = {"entities": [  # sale of a black male donkey (damaged tail)
    E("PERSON", "Οὐαλέριος Ἡρακλῆς"), E("OCCUPATION", "ὀφφικιάλιος"),
    E("PERSON", "Οὐαλερίου Ποιμενίου"), E("OCCUPATION", "ἐπιτρόπου\nπριουάτης"),
    E("PLACE", "Θηβαΐδος"), E("PLACE", "Ἑρμοπολίτῃ"),
    E("PERSON", "Αὐρηλίῳ\nἈπολλωνίῳ Σαραπίωνος", None, "buyer"),
    E("PLACE", "Ὀξυρυγχιτῶν\nπόλεως"),
    E("TRANSACTION", "ἐώνησαι", None, "t1"),
    E("PERSON", "Βησᾶ Ἱέρακος", None, "seller"), E("PERSON", "Ταϊέρακος"),
    E("PLACE", "Πανὸς πόλεως"),
    E("COMMODITY", "ὄνον ἄρρενα μελανόχροον τέλειον"),
], "relations": [
    ("buyer", "t1", "PARTY_OF"), ("seller", "t1", "PARTY_OF"),
]}

SPEC["22137"] = {"entities": [  # land-tax register: arouras + denarii-myriads (double)
    E("PERSON", "Ἀμμωνιανὸς"),
    E("UNIT", "ἄρουραι", "Ἀμμωνιανὸς ἄρουραι", "u1"), E("QUANTITY", "ροθ", "ἄρουραι ροθ", "q1"),
    E("FRACTION", "δ", "ροθ δ"),
    E("CURRENCY", "μυριάδες", "ροθ δ δηναρίων\nμυριάδες", "cur1"),
    E("UNIT", "ἄρουραι", "ων ἄρουραι ρλγ", "u2"), E("QUANTITY", "ρλγ", "ἄρουραι ρλγ", "q2"),
    E("FRACTION", "δ", "ρλγ δ"), E("FRACTION", "η", "δ η ιϛ"), E("FRACTION", "ιϛ", "η ιϛ"),
    E("CURRENCY", "μυριάδες", "ιϛ\nδηναρίων μυριάδες ρ", "cur2"), E("MONEY_AMOUNT", "ρ", "μυριάδες ρ", "mm2"),
    E("OCCUPATION", "ὀφφικιάλιος", "θεος ὀφφικιάλιος"),
    E("UNIT", "ἄρουραι", "καθολικῆς ἄρουραι νγ", "u3"), E("QUANTITY", "νγ", "ἄρουραι νγ", "q3"),
    E("FRACTION", "𐅵", "νγ 𐅵"), E("FRACTION", "δ", "𐅵 δ η"), E("FRACTION", "η", "δ η ιϛ δηναρίων"), E("FRACTION", "ιϛ", "η ιϛ δηναρίων"),
    E("CURRENCY", "μυριάδες", "ιϛ δηναρίων\nμυριάδες ξ", "cur3"), E("MONEY_AMOUNT", "ξ", "μυριάδες ξ", "mm3"),
    E("PERSON_ROLE", "διασημότατος"),
    E("UNIT", "ἄρουραι", "διασημότατος ἄρουραι η", "u4"), E("QUANTITY", "η", "ἄρουραι η δηναρίων", "q4"),
    E("CURRENCY", "μυριάδες", "η δηναρίων\nμυριάδες θ", "cur4"), E("MONEY_AMOUNT", "θ", "μυριάδες θ", "mm4"),
    E("OCCUPATION", "βενεφικιάριος", "βενεφικιάριος\nἄρουραι σογ"),
    E("UNIT", "ἄρουραι", "βενεφικιάριος\nἄρουραι σογ", "u5"), E("QUANTITY", "σογ", "ἄρουραι σογ", "q5"),
    E("FRACTION", "𐅵", "σογ 𐅵"), E("FRACTION", "δ", "𐅵 δ ξδ"), E("FRACTION", "ξδ", "δ ξδ"),
    E("CURRENCY", "μυριάδες", "ξδ δηναρίων μυριάδες\nτ", "cur5"), E("MONEY_AMOUNT", "τ", "μυριάδες\nτ", "mm5"),
    E("PERSON", "Ἀπολλώνιος"), E("OCCUPATION", "βενεφικιάριος", "Ἀπολλώνιος βενεφικιάριος"),
    E("UNIT", "ἄρουραι", "βενεφικιάριος\nἄρουραι ρλε", "u6"), E("QUANTITY", "ρλε", "ἄρουραι ρλε", "q6"),
    E("CURRENCY", "μυριάδες", "ρλε δηνναρίων μυριάδες\nρ", "cur6"), E("MONEY_AMOUNT", "ρ", "μυριάδες\nρ", "mm6"),
    E("UNIT", "ἄρουραι", "γένους ἄρουραι", "u7"), E("QUANTITY", "ϙ", "ἄρουραι …ϙ", "q7"),
    E("FRACTION", "δ", "ϙ δ\nδηναρίων"),
    E("CURRENCY", "μυριάδες", "δ\nδηναρίων μυριάδες", "cur7"),
    E("OCCUPATION", "ὀφφικιάλιος", "ων ὀφφικιάλιος ἄρουραι"),
    E("UNIT", "ἄρουραι", "ὀφφικιάλιος ἄρουραι\nϙβ", "u8"), E("QUANTITY", "ϙβ", "ἄρουραι\nϙβ", "q8"),
    E("CURRENCY", "μυριάδες", "ϙβ δηναρίων μυριάδες ρ", "cur8"), E("MONEY_AMOUNT", "ρ", "μυριάδες ρ", "mm8"),
    E("PERSON", "Ὡριγένους", "Ὡριγένους … ἄρουραι"),
    E("UNIT", "ἄρουραι", "Ὡριγένους … ἄρουραι …υκα", "u9"), E("QUANTITY", "υκα", "ἄρουραι …υκα", "q9"),
    E("FRACTION", "𐅵", "υκα 𐅵"), E("FRACTION", "δ", "𐅵 δ\nδηναρίων"),
    E("CURRENCY", "μυριάδες", "δ\nδηναρίων μυριάδες υ", "cur9"), E("MONEY_AMOUNT", "υ", "μυριάδες υ", "mm9"),
    E("PERSON_ROLE", "γυνὴ", "γυνὴ Ὡριγένους"), E("PERSON", "Ὡριγένους", "γυνὴ Ὡριγένους"),
    E("UNIT", "ἄρουραι", "Ὡριγένους … ἄρουραι\nπϛ", "u10"), E("QUANTITY", "πϛ", "ἄρουραι\nπϛ", "q10"),
    E("FRACTION", "𐅵", "πϛ 𐅵"), E("FRACTION", "δ", "𐅵 δ η"), E("FRACTION", "η", "δ η δηναρίων"),
    E("CURRENCY", "μυριάδες", "η δηναρίων μυριάδες ρ", "cur10"), E("MONEY_AMOUNT", "ρ", "μυριάδες ρ", "mm10"),
    E("PERSON", "Σαραποδωρ"),
    E("UNIT", "ἄρουραι", "Σαραποδωρ… ἄρουραι\nροε", "u11"), E("QUANTITY", "ροε", "ἄρουραι\nροε", "q11"),
    E("FRACTION", "𐅵", "ροε 𐅵"),
    E("CURRENCY", "μυριάδες", "ροε 𐅵 δηναρίων μυριάδες", "cur11"),
    E("PERSON", "Γεροντίου", "γυνὴ Γεροντίου"),
    E("PERSON", "Ὑάκινθος", "καὶ Ὑάκινθος"),
    E("UNIT", "ἄρουραι", "πραιποσίτων ἄρουραι\nρ", "u12"), E("QUANTITY", "ρ", "ἄρουραι\nρ… δηναρίων", "q12"),
    E("OCCUPATION", "βοηθὸς", "βοηθὸς Ἀλεξάνδρου"), E("PERSON", "Ἀλεξάνδρου", "βοηθὸς Ἀλεξάνδρου"),
    E("UNIT", "ἄρουραι", "Ἀλεξάνδρου ἄρουραι\nρκθ", "u13"), E("QUANTITY", "ρκθ", "ἄρουραι\nρκθ", "q13"),
    E("FRACTION", "λβ", "ρκθ λβ"),
    E("CURRENCY", "μυριάδες", "ρκθ λβ δηναρίων μυριάδες ρ", "cur13"), E("MONEY_AMOUNT", "ρ", "μυριάδες ρ…", "mm13"),
    E("PERSON", "Ζωΐλου", "ς Ζωΐλου ἄρουραι"),
    E("UNIT", "ἄρουραι", "Ζωΐλου ἄρουραι λβ", "u14"), E("QUANTITY", "λβ", "ἄρουραι λβ 𐅵", "q14"),
    E("FRACTION", "𐅵", "λβ 𐅵 ιϛ"), E("FRACTION", "ιϛ", "𐅵 ιϛ λβ"), E("FRACTION", "λβ", "ιϛ λβ\nδηναρίων"),
    E("CURRENCY", "μυριάδες", "λβ\nδηναρίων μυριάδες", "cur14"),
    E("UNIT", "ἄρουραι", "α ἄρουραι λγ", "u15"), E("QUANTITY", "λγ", "ἄρουραι λγ 𐅵", "q15"),
    E("FRACTION", "𐅵", "λγ 𐅵 δ"), E("FRACTION", "δ", "𐅵 δ η ιϛ"), E("FRACTION", "η", "δ η ιϛ λβ"),
    E("FRACTION", "ιϛ", "η ιϛ λβ"), E("FRACTION", "λβ", "ιϛ λβ\nδηναρίων"),
    E("CURRENCY", "μυριάδες", "λβ\nδηναρίων μυριάδες", "cur15"),
    E("PERSON", "Δημαρέως"),
    E("UNIT", "ἄρουραι", "Δημαρέως ἄρουραι ιγ", "u16"), E("QUANTITY", "ιγ", "ἄρουραι ιγ 𐅵", "q16"),
    E("FRACTION", "𐅵", "ιγ 𐅵\nδηναρίων"),
    E("CURRENCY", "μυριάδες", "𐅵\nδηναρίων μυριάδες ι", "cur16"), E("MONEY_AMOUNT", "ι", "μυριάδες ι", "mm16"),
    E("OCCUPATION", "κεφαλαιωτής"),
    E("UNIT", "ἄρουραι", "κεφαλαιωτής ἄρουραι ριζ", "u17"), E("QUANTITY", "ριζ", "ἄρουραι ριζ", "q17"),
    E("FRACTION", "ιϛ", "ριζ ιϛ"),
    E("CURRENCY", "μυριάδες", "ριζ ιϛ\nδηναρίων μυριάδες ρ", "cur17"), E("MONEY_AMOUNT", "ρ", "μυριάδες ρ", "mm17"),
    E("PERSON", "Ἀμμωνίου", "Ἀμμωνίου ἄρουραι"),
    E("UNIT", "ἄρουραι", "Ἀμμωνίου ἄρουραι", "u18"),
], "relations": [
    ("q1", "u1", "HAS_UNIT"), ("q2", "u2", "HAS_UNIT"), ("mm2", "cur2", "HAS_CURRENCY"),
    ("q3", "u3", "HAS_UNIT"), ("mm3", "cur3", "HAS_CURRENCY"),
    ("q4", "u4", "HAS_UNIT"), ("mm4", "cur4", "HAS_CURRENCY"),
    ("q5", "u5", "HAS_UNIT"), ("mm5", "cur5", "HAS_CURRENCY"),
    ("q6", "u6", "HAS_UNIT"), ("mm6", "cur6", "HAS_CURRENCY"),
    ("q7", "u7", "HAS_UNIT"),
    ("q8", "u8", "HAS_UNIT"), ("mm8", "cur8", "HAS_CURRENCY"),
    ("q9", "u9", "HAS_UNIT"), ("mm9", "cur9", "HAS_CURRENCY"),
    ("q10", "u10", "HAS_UNIT"), ("mm10", "cur10", "HAS_CURRENCY"),
    ("q11", "u11", "HAS_UNIT"),
    ("q12", "u12", "HAS_UNIT"),
    ("q13", "u13", "HAS_UNIT"), ("mm13", "cur13", "HAS_CURRENCY"),
    ("q14", "u14", "HAS_UNIT"),
    ("q15", "u15", "HAS_UNIT"),
    ("q16", "u16", "HAS_UNIT"), ("mm16", "cur16", "HAS_CURRENCY"),
    ("q17", "u17", "HAS_UNIT"), ("mm17", "cur17", "HAS_CURRENCY"),
]}

SPEC["2221"] = {"entities": [  # private letter (Zenon archive; damaged)
    E("PERSON", "Κρίτωνι", "Κρίτωνι χαίρειν"),
    E("PERSON", "Θεόπομπος"), E("PLACE", "Πτολεμαίδα"),
    E("PERSON", "Ζήνωνα"),
    E("DATE_REF", "ἔτους γ"),
    E("PERSON", "Κρίτωνι"),
], "relations": []}

SPEC["2226"] = {"entities": [  # private letter (Zenon archive; damaged, blind)
    E("PERSON", "βασιλεὺς", "ὁ βασιλεὺς"),
    E("PLACE", "Ἀλεξανδρείαι"), E("PERSON", "Κύρου", "τὸ Κύρου"),
    E("PERSON", "Σαραπίωνος", "διὰ Σαραπίωνος"),
    E("QUANTITY", "ιε", "ιε γίνονται κγ"),
    E("QUANTITY", "κγ", "ιε γίνονται κγ"),
    E("PERSON", "Θαλιάρχωι"), E("PERSON", "Ἀπολλωνίου"),
    E("PLACE", "Ἀλεξάνδρου νήσωι"),
    E("OCCUPATION", "ἀρχιφυλακίτην"),
    E("DATE_REF", "κγ τοῦ Μεχεὶρ"),
], "relations": []}

SPEC["2233"] = {"entities": [  # tax/contribution list + sheep register (blind)
    E("PERSON", "Θεόδωρος Λέοντος"), E("PLACE", "Σολεύς"),
    E("CURRENCY", "δραχμαὶ", "Σολεύς δραχμαὶ ξα", "d1"), E("MONEY_AMOUNT", "ξα", "δραχμαὶ ξα", "m1"),
    E("MONEY_AMOUNT", "διώβολον", "ξα διώβολον"),
    E("PERSON", "Ἀριστοκλῆς Νικάνδρου"), E("PLACE", "Λάκων"),
    E("CURRENCY", "δραχμαὶ", "Λάκων δραχμαὶ οε", "d2"), E("MONEY_AMOUNT", "οε", "δραχμαὶ οε διώβολον\nἸάσων", "m2"),
    E("MONEY_AMOUNT", "διώβολον", "οε διώβολον\nἸάσων"),
    E("PERSON", "Ἰάσων Κερκίωνος"), E("PLACE", "Καλυνδεὺς"),
    E("CURRENCY", "δραχμαὶ", "Καλυνδεὺς δραχμαὶ οε", "d3"), E("MONEY_AMOUNT", "οε", "Καλυνδεὺς δραχμαὶ οε", "m3"),
    E("MONEY_AMOUNT", "διώβολον", "δραχμαὶ οε διώβολον\nἈμῶς"),
    E("PERSON", "Ἀμῶς Πετήσιος"), E("PLACE", "Ἀφροδιτοπολίτης"),
    E("CURRENCY", "δραχμαὶ", "Ἀφροδιτοπολίτης δραχμαὶ λε", "d4"), E("MONEY_AMOUNT", "λε", "δραχμαὶ λε", "m4"),
    E("MONEY_AMOUNT", "διώβολον", "λε διώβολον"),
    E("PERSON", "Ἑρμογένης Ἀντιλόχου"), E("PLACE", "Σικελός"),
    E("CURRENCY", "δραχμαὶ", "Σικελός δραχμαὶ οε", "d5"), E("MONEY_AMOUNT", "οε", "Σικελός δραχμαὶ οε", "m5"),
    E("MONEY_AMOUNT", "διώβολον", "δραχμαὶ οε διώβολον\nΔιονυσόδωρος"),
    E("PERSON", "Διονυσόδωρος"),
    E("CURRENCY", "δραχμαὶ", "αὐτοῦ\nδραχμαὶ νε", "d6"), E("MONEY_AMOUNT", "νε", "δραχμαὶ νε διώβολον", "m6"),
    E("MONEY_AMOUNT", "διώβολον", "νε διώβολον\n"),
    E("PERSON", "Ἀμμώνιος Θέωνος"), E("PLACE", "Κυρηναῖος"),
    E("CURRENCY", "δραχμαὶ", "Κυρηναῖος δραχμαὶ νε", "d7"), E("MONEY_AMOUNT", "νε", "Κυρηναῖος δραχμαὶ νε", "m7"),
    E("MONEY_AMOUNT", "πεντώβολον", "νε πεντώβολον"),
    E("PERSON", "Πετερμούθης Νεχθῶτος"), E("PLACE", "Ὑψηλοκωμίτης"),
    E("CURRENCY", "δραχμαὶ", "Ὑψηλοκωμίτης δραχμαὶ νε", "d8"), E("MONEY_AMOUNT", "νε", "Ὑψηλοκωμίτης δραχμαὶ νε", "m8"),
    E("MONEY_AMOUNT", "ὀβολὸς τέταρτον", "νε ὀβολὸς τέταρτον"),
    E("PLACE", "Φιλαδελφείαι"), E("COMMODITY", "προβάτων", None, "sheep"),
    E("PERSON", "Πετέσιτος", "Πετέσιτος ϛ"), E("QUANTITY", "ϛ", "Πετέσιτος ϛ", "sq1"),
    E("PERSON", "Πᾶσις Παοῦ"), E("QUANTITY", "ιη", "Πᾶσις Παοῦ ιη", "sq2"),
    E("PERSON", "Σεαρμῶσις"), E("QUANTITY", "ε", "Σεαρμῶσις ε", "sq3"),
    E("PERSON", "Ζήνωνος", "καὶ Ζήνωνος ρ"), E("QUANTITY", "ρ", "Ζήνωνος ρ", "sq4"),
    E("PERSON", "Θεόδοτος"), E("PERSON", "Ζήνωνος", "τὰ Ζήνωνος μ"), E("QUANTITY", "μ", "Ζήνωνος μ", "sq5"),
    E("PERSON", "Βοτρῆς"), E("QUANTITY", "ι", "Βοτρῆς ι", "sq6"),
    E("PERSON", "Σωστράτου"), E("QUANTITY", "ρ", "Σωστράτου ρ", "sq7"),
    E("PERSON", "Σεαρμώσιος"),
    E("CURRENCY", "δραχμὰς", "Σεαρμώσιος δραχμὰς ξ", "pd1"), E("MONEY_AMOUNT", "ξ", "δραχμὰς ξ", "pm1"),
    E("PERSON", "Πάσιτος Παοῦτος"), E("MONEY_AMOUNT", "μβ", "Παοῦτος μβ τριώβολον", "pm2"),
    E("MONEY_AMOUNT", "τριώβολον", "μβ τριώβολον"),
    E("PERSON", "Βοτρέους"), E("MONEY_AMOUNT", "κ", "Βοτρέους κ", "pm3"),
    E("PERSON", "Σισίνου"), E("MONEY_AMOUNT", "ιγ", "Σισίνου ιγ", "pm4"),
    E("PERSON", "Πετέσιτος", "παρὰ Πετέσιτος ιη"), E("MONEY_AMOUNT", "ιη", "Πετέσιτος ιη", "pm5"),
    E("PERSON", "Πέτεσις"), E("PERSON", "Ὥρου", "παρʼ Ὥρου"),
    E("CURRENCY", "δραχμὰς", "Ὥρου\nδραχμὰς β", "pd2"), E("MONEY_AMOUNT", "β", "δραχμὰς β τετρώβολον", "pm6"),
    E("MONEY_AMOUNT", "τετρώβολον", "β τετρώβολον"),
    E("PERSON", "Στεφάνου"), E("MONEY_AMOUNT", "β", "Στεφάνου β", "pm7"),
    E("PERSON", "Ἰάσονος"), E("MONEY_AMOUNT", "ϛ", "Ἰάσονος ϛ", "pm8"),
    E("MONEY_AMOUNT", "β", "β διώβολον", "pm9"), E("MONEY_AMOUNT", "διώβολον", "β διώβολον"),
], "relations": [
    ("m1", "d1", "HAS_CURRENCY"), ("m2", "d2", "HAS_CURRENCY"), ("m3", "d3", "HAS_CURRENCY"),
    ("m4", "d4", "HAS_CURRENCY"), ("m5", "d5", "HAS_CURRENCY"), ("m6", "d6", "HAS_CURRENCY"),
    ("m7", "d7", "HAS_CURRENCY"), ("m8", "d8", "HAS_CURRENCY"),
    ("pm1", "pd1", "HAS_CURRENCY"), ("pm6", "pd2", "HAS_CURRENCY"),
    ("sheep", "sq1", "HAS_QUANTITY"), ("sheep", "sq2", "HAS_QUANTITY"),
    ("sheep", "sq3", "HAS_QUANTITY"), ("sheep", "sq4", "HAS_QUANTITY"),
    ("sheep", "sq5", "HAS_QUANTITY"), ("sheep", "sq6", "HAS_QUANTITY"),
    ("sheep", "sq7", "HAS_QUANTITY"),
]}


def _locate(text: str, surface: str, ctx: str | None, doc_id: str) -> int:
    """Find a surface string, disambiguated by an optional wider context."""
    if ctx:
        c = text.find(ctx)
        if c == -1:
            raise SystemExit(f"{doc_id}: context {ctx!r} not found")
        start = text.find(surface, c, c + len(ctx))
    else:
        start = text.find(surface)
    if start == -1:
        raise SystemExit(f"{doc_id}: surface {surface!r} not found")
    return start


def build(text: str, spec: dict, doc_id: str) -> tuple[list, list, list]:
    entities, keys, pos = [], {}, 0
    for label, surface, ctx, key in spec["entities"]:
        if ctx:
            # The context may begin before the previous span ends (a unit and
            # its numeral), so allow it to overlap backwards — but the surface
            # itself must still lie at or after `pos`.
            c = text.find(ctx, max(0, pos - len(ctx)))
            if c == -1:
                raise SystemExit(f"{doc_id}: context {ctx!r} not found near {pos}")
            start = text.find(surface, max(c, pos), c + len(ctx))
        else:
            start = text.find(surface, pos)
        if start == -1:
            raise SystemExit(f"{doc_id}: surface {surface!r} not found from {pos}")
        end = start + len(surface)
        if key:
            keys[key] = len(entities)
        entities.append({"start": start, "end": end, "label": label, "text": text[start:end]})
        pos = end
    relations = [
        {"head": keys[h], "tail": keys[t], "type": ty} for h, t, ty in spec["relations"]
    ]
    skips = []
    for surface, reason, ctx in spec.get("skips", []):
        start = _locate(text, surface, ctx, doc_id)
        skips.append(
            {"start": start, "end": start + len(surface), "text": surface, "reason": reason}
        )
    return entities, relations, skips


def main() -> None:
    with Path("data/gold/to_annotate.jsonl").open(encoding="utf-8") as fh:
        batch = {json.loads(line)["doc_id"]: json.loads(line) for line in fh}
    out = []
    for doc_id, spec in SPEC.items():
        src = batch[doc_id]
        ents, rels, skips = build(src["text"], spec, doc_id)
        doc = {
            "doc_id": doc_id,
            "text": src["text"],
            "meta": {**src["meta"], "annotator": "claude-opus-4-8", "provenance": "model_draft"},
            "entities": ents,
            "relations": rels,
            "double_annotate": src["double_annotate"],
        }
        if skips:
            doc["skipped_numerals"] = skips
        out.append(doc)
    path = Path("data/gold/annotated.jsonl")
    path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in out) + "\n",
                    encoding="utf-8")
    print(f"wrote {len(out)} documents, "
          f"{sum(len(d['entities']) for d in out)} entities, "
          f"{sum(len(d['relations']) for d in out)} relations -> {path}")


if __name__ == "__main__":
    main()
