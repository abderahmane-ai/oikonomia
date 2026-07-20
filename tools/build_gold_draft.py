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
    E("DATE_REF", "ὑπατείας τοῦ δεσπότου ἡμῶν Μαξιμίνου τοῦ ἐπιφανεστάτου\nΚαίσαρος", None, "date"),
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
    E("DATE_REF", "ὑπατείας τῶν δεσποτῶν ἡμῶν Ὁνωρίου\nτὸ ι καὶ Θεοδοσίου τὸ ϛ τῶν αἰωνίων Αὐγούστων"),
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
], "relations": []}

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
    E("DATE_REF", "κη", "κη Ἀρτεμιδώρωι"),
    E("PERSON", "Ἀρτεμιδώρωι"), E("OCCUPATION", "ἐπιστολογράφωι"),
    E("OCCUPATION", "ἱερεῦσι"), E("PERSON", "Ἑρμοφάντωι"),
    E("COMMODITY", "Κνιδίου", None, "c10"),
    E("UNIT", "κοτύλαι", None, "u10"), E("QUANTITY", "ϛ", "κοτύλαι ϛ", "q10"),
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
    E("DATE_REF", "ἔτους ὀγδόου\nΤιβερίου Κλαυδίου Καίσαρος\nΣεβαστοῦ Γερμανικοῦ\nΑὐτοκράτορος Φαρμοῦθι ιδ", None, "date"),
], "relations": [("q1", "u1", "HAS_UNIT"),
    ("p1", "t1", "PARTY_OF"), ("p2", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO")]}

SPEC["12583"] = {"entities": [
    E("DATE_REF", "ἔτους τρεισκαιδεκάτου Αὐτοκράτορος Καίσαρος Τίτου Αἰλίου Ἁδριανοῦ Ἀντωνίνου Σεβαστοῦ\nΕὐσεβοῦς μηνὸς Σεβαστοῦ κζ Θὼθ κζ", None, "date"),
    E("PLACE", "Ἱερᾷ Νήσῳ"), E("PLACE", "Ἡρακλείδου μερίδος"), E("PLACE", "Ἀρσινοΐτου νομοῦ"),
    E("TRANSACTION", "ὁμολογεῖ", None, "t1"),
    E("PERSON", "Πτολεμαὶς Χαιρήμονος τοῦ Χαιρήμονος", None, "p_seller"),
    E("PLACE", "ἀμφόδου Φρεμεὶ"),
    E("AGE", "πεντήκοντα ὀκτὼ"),
    E("PERSON", "Κέλερος Ἀφροδισίου"),
    E("PERSON", "Ἰουλίῳ Μαξίμῳ", None, "p_lender"),
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
    E("DATE_REF", "τρεισκαιδεκάτου ἔτους Ἀντωνίνου Καίσαρος"),
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
    E("DATE_REF", "ιη ἔτος\nἉδριανοῦ Καίσαρος τοῦ κυρίου"),
    E("COMMODITY", "νομὴν ὑπολόγων καὶ ῥαχοῦ", None, "c2"),
    E("PLACE", "Ψενύρεως"),
    E("CURRENCY", "ἀργυρίου"),
    E("CURRENCY", "δραχμὰς", None, "d2"), E("MONEY_AMOUNT", "εἴκοσι", None, "m2"),
    E("PERSON", "Ἁρυώθης"),
    E("DATE_REF", "ἔτους ιζ\nΑὐτοκράτορος Καίσαρος Τραϊανοῦ\nἉδριανοῦ Σεβαστοῦ, Ἐπεὶφ η", None, "date"),
    E("PERSON", "Βησαρίων"), E("OCCUPATION", "ὑπηρέτης"),
], "relations": [
    ("m1", "d1", "HAS_CURRENCY"), ("c1", "m1", "HAS_PRICE"),
    ("m2", "d2", "HAS_CURRENCY"), ("c2", "m2", "HAS_PRICE"),
    ("p1", "t1", "PARTY_OF"), ("t1", "date", "DATED_TO"),
]}

SPEC["12769"] = {"entities": [
    E("PERSON", "Στοτοῆτι Στοτοήτεως", None, "p1"),
    E("PERSON", "Ὥρου τοῦ Τεσενούφεως τοῦ Τεσενούφεως", None, "p2"),
    E("TRANSACTION", "μισθώσασθαι", None, "t1"),
    E("PLACE", "κώμῃ Ἡρακλείᾳ"),
    E("COMMODITY", "ἐλαιουργεῖον"),
    E("DATE_REF", "μηνὸς Σωτηρίου νουμηνίας"),
    E("DATE_REF", "πεντεκαιδεκάτου ἔτους Αὐτοκράτορος\nΚαίσαρος Δομιτιανοῦ Σεβαστοῦ Γερμανικοῦ", None, "date"),
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
    E("DATE_REF", "ἔτους ιθ Αὐτοκρατόρων Καισάρων Μάρκου Αὐρηλίου\nἈντωνίνου καὶ Πουβλίου Σεπτιμίου Γέτα\nΒρεταννικῶν Μεγίστων Εὐσεβῶν Σεβαστῶν"),
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


def build(text: str, spec: dict, doc_id: str) -> tuple[list, list]:
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
    return entities, relations


def main() -> None:
    with Path("data/gold/to_annotate.jsonl").open(encoding="utf-8") as fh:
        batch = {json.loads(line)["doc_id"]: json.loads(line) for line in fh}
    out = []
    for doc_id, spec in SPEC.items():
        src = batch[doc_id]
        ents, rels = build(src["text"], spec, doc_id)
        out.append({
            "doc_id": doc_id,
            "text": src["text"],
            "meta": {**src["meta"], "annotator": "claude-opus-4-8", "provenance": "model_draft"},
            "entities": ents,
            "relations": rels,
            "double_annotate": src["double_annotate"],
        })
    path = Path("data/gold/annotated.jsonl")
    path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in out) + "\n",
                    encoding="utf-8")
    print(f"wrote {len(out)} documents, "
          f"{sum(len(d['entities']) for d in out)} entities, "
          f"{sum(len(d['relations']) for d in out)} relations -> {path}")


if __name__ == "__main__":
    main()
