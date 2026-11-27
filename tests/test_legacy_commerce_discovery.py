import unittest
from datetime import date
from scripts.xfit_legacy_commerce_discovery import LANES, assess, route_for, existing_route

def row(pid,title,slug,body=None,modified="2026-10-01T10:00:00"):
    return {"id":pid,"slug":slug,"status":"publish","link":"https://xfit.cz/"+slug+"/",
        "title":{"raw":title},"content":{"raw":body or "<p>Original article.</p>"*100},
        "modified":modified}

class LegacyCommerceDiscoveryTests(unittest.TestCase):
    def test_exact_intent_routing_and_exclusion(self):
        rows = {lane:[] for lane in LANES}
        rows["creatine"] = [
            row(501,"Jak koupit kreatin","jak-koupit-kreatin"),
            row(502,"Kreatin a rizika: jak vybrat","kreatin-rizika"),
            row(503,"Jak vybrat kreatin a protein","kreatin-protein"),
            row(504,"Jak koupit kreatin","jiny-kreatin",modified="2026-11-25T10:00:00"),
        ]
        rows["whey"] = [row(505,"Jak vybrat syrovátkový protein","whey-vyber"),
                        row(506,"Jak vybrat rostlinný protein","plant-vyber")]
        rows["plant"] = rows["whey"]
        rows["mat"] = [row(507,"Jak vybrat podložku na cvičení","podlozka-cviceni"),
                       row(508,"Jak vybrat podložku pod auto","podlozka-auto")]
        rows["band"] = [row(509,"Jak vybrat odporové gumy","odporove-gumy")]
        result=assess(rows,today=date(2026,11,27))
        self.assertEqual([[c["id"] for c in result[l]["review_candidates"]] for l in LANES],
                         [[501],[505],[506],[507],[509]])
        self.assertEqual(result["creatine"]["recent_or_unknown_modified"],1)
        self.assertTrue(all(c["traffic"]=="UNKNOWN" for l in LANES for c in result[l]["review_candidates"]))

    def test_relative_fragment_and_query_are_already_linked(self):
        source="https://xfit.cz/article/"
        target="xfit-os-vybaveni-na-domaci-cviceni-nabidky"
        self.assertTrue(existing_route('<a href="/'+target+'/#xfit-gear-mat">link</a>',source,target))
        self.assertFalse(existing_route('<a href="https://evil.cz/'+target+'/">link</a>',source,target))
        self.assertFalse(existing_route('/'+target+'/',source,target))
    def test_no_medical_or_generic_protein_and_no_prior_release(self):
        self.assertFalse(route_for("nejlepsi protein pri alergii","whey"))
        self.assertFalse(route_for("jak vybrat protein","whey"))
        self.assertFalse(route_for("kdy zacit s kreatinem v centru","creatine"))
        rows={lane:[] for lane in LANES}
        rows["creatine"]=[row(10854,"Jak koupit kreatin","kreatin-test"),row(10860,"Slevy na kreatin a cena","kreatin-slevy")]
        self.assertEqual(assess(rows,today=date(2026,11,27))["creatine"]["prior_allowlist"],2)

if __name__ == "__main__":
    unittest.main()
