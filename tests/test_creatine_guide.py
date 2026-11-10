import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from scripts.xfit_creatine_guide import (
    build_document, build_tracked_url, shortlist, validate_example,
)
from scripts.wp_publish import PublishError

BASE=("https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com"
      "&utm_source=pap&a_aid=TESTAID&a_bid=TESTBID")
SAMPLE=("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
        "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
        "&utm_source=pap&a_aid=TESTAID&a_bid=TESTBID")

def item(id, name, price, mass):
    return {
        "id": str(id), "title": name, "price_czk": price,
        "mass_g":mass,"category":"Kreatin", "merchant":"NaMaximum.cz",
        "ean":str(id),
        "source_url":"https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant="+str(id),
        "image_url":"https://greenmedical.bwcdn.net/media/example.jpg",
    }

class CreatineGuideTests(unittest.TestCase):
    def setUp(self):
        self.catalog={"merchant":"namaximum.cz","merchant_match":True,"products":[
            item(392,"Creatine Pure Creapure 1kg",900,1000),
            item(401,"Kreatin Monohydrat 500g",430,500),
            item(402,"Creatine Monohydrate 250g",270,250),
            item(403,"Creatine Monohydrate Complex 500g",180,500),
            item(404,"Creatine Creatine 500g",420,500),
        ]}
    def test_sample(self):
        self.assertTrue(validate_example(BASE,SAMPLE))
    def test_correct_target_and_no_heureka(self):
        link=build_tracked_url(
           "https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392",
           BASE,SAMPLE)
        self.assertIn("variant=392",link)
        self.assertIn("a_aid=TESTAID",link)
        self.assertNotIn("heureka",link)
    def test_sample_homepage_fails(self):
        with self.assertRaises(ValueError):
            validate_example(BASE,SAMPLE.replace("/kategorie/kreatin/creatine-creapure","/"))
    def test_other_host_fails(self):
        with self.assertRaises(PublishError):
            build_tracked_url("https://other.example/p",BASE,SAMPLE)
    def test_unknown_param_fails(self):
        with self.assertRaises(PublishError):
            build_tracked_url("https://www.namaximum.cz/p?evil=yes",BASE,SAMPLE)
    def test_affiliate_url_must_be_exact_single_product_destination(self):
        # Previously these could be tracked as if they were product offers.
        for invalid in (
            "https://www.namaximum.cz/",
            "https://www.namaximum.cz:8443/p/creatine?variant=392",
            "https://www.namaximum.cz//redirect-product?variant=392",
            "https://www.namaximum.cz/p/creatine?variant=392&variant=401",
            "https://www.namaximum.cz/p/creatine?VARIANT=392",
            "https://www.namaximum.cz/p/creatine?variant=",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(PublishError):
                    build_tracked_url(invalid, BASE, SAMPLE)
        valid="https://www.namaximum.cz/p/creatine?variant=392"
        self.assertIn("variant=392",build_tracked_url(valid,BASE,SAMPLE))

    def test_nonstandard_port_in_approved_example_is_rejected(self):
        invalid=SAMPLE.replace("www.namaximum.cz/", "www.namaximum.cz:8443/")
        with self.assertRaises(PublishError):
            validate_example(BASE,invalid)
    def test_shortlist_and_transparency(self):
        guide=build_document(self.catalog,BASE,SAMPLE)
        self.assertIn('rel="sponsored nofollow noopener noreferrer"',guide["content"])
        self.assertIn("Cena za 100 g",guide["content"])
        self.assertNotIn("Creatine Monohydrate Complex",guide["content"])
        self.assertGreater(len(guide["content"]),2500)
        self.assertEqual(guide["slug"],"xfit-os-kreatin-poradce")
    def test_price_priority_links_resolve_to_two_valid_product_cards(self):
        from html.parser import HTMLParser
        class PickParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = set()
                self.priorities = []
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "article" and values.get("id"):
                    self.ids.add(values["id"])
                if tag == "a" and values.get("href","").startswith("#xfit-offer-"):
                    self.priorities.append(values["href"][1:])
        rendered = build_document(self.catalog,BASE,SAMPLE)["content"]
        parser = PickParser()
        parser.feed(rendered)
        self.assertGreaterEqual(len(parser.priorities),2)
        self.assertIn('id="xfit-vyber-podle-rozpoctu"',rendered)
        self.assertIn("Kolik chcete maximálně utratit?",rendered)
        self.assertIn("v tomto přehledu",rendered)
        self.assertTrue(all(anchor in parser.ids for anchor in parser.priorities))
        self.assertIn("Nejnižší výdaj při nákupu",rendered)
        self.assertIn("Nejnižší cena za 100 g prášku",rendered)
        self.assertIn("pokud doplněk nepotřebujete",rendered)
        self.assertNotIn("nejlevnější na trhu",rendered)

    def test_unchanged_wp_post_requires_fresh_public_body(self):
        from unittest.mock import patch
        from scripts.xfit_creatine_guide import publish_if_changed
        from scripts.wp_publish import MARKER
        doc = build_document(self.catalog, BASE, SAMPLE)
        post = {"id":25455,"slug":doc["slug"],"status":"publish",
                "content":{"raw":MARKER+"\n"+doc["content"]},
                "link":"https://xfit.cz/xfit-os-kreatin-poradce/"}
        with patch("scripts.xfit_creatine_guide.normalized_base",return_value="https://xfit.cz"), \
             patch("scripts.xfit_creatine_guide.wp_request",return_value=[post]), \
             patch("scripts.xfit_creatine_guide.verify_public",return_value=True) as public, \
             patch("scripts.xfit_creatine_guide.publish") as writer:
            result = publish_if_changed(doc)
        self.assertEqual(result["state"],"unchanged_public_verified")
        public.assert_called_once_with(post["link"],doc["title"],MARKER+"\n"+doc["content"])
        writer.assert_not_called()

    def test_stale_cached_public_body_never_reports_unchanged_success(self):
        from unittest.mock import patch
        from scripts.xfit_creatine_guide import publish_if_changed
        from scripts.wp_publish import MARKER
        doc = build_document(self.catalog, BASE, SAMPLE)
        post = {"id":25455,"slug":doc["slug"],"status":"publish",
                "content":{"raw":MARKER+"\n"+doc["content"]},
                "link":"https://xfit.cz/xfit-os-kreatin-poradce/"}
        with patch("scripts.xfit_creatine_guide.normalized_base",return_value="https://xfit.cz"), \
             patch("scripts.xfit_creatine_guide.wp_request",return_value=[post]), \
             patch("scripts.xfit_creatine_guide.verify_public",side_effect=PublishError("cached older version")), \
             patch("scripts.xfit_creatine_guide.publish") as writer:
            with self.assertRaisesRegex(PublishError,"cached older version"):
                publish_if_changed(doc)
        writer.assert_not_called()

    def test_full_feed_cheapest_small_creatine_pack_survives_unit_top_150(self):
        # The 150 cheapest per-100g options (all 1kg) must not suppress the
        # genuine lowest upfront 200g source offer before editorial grouping.
        products=[]
        for i in range(150):
            ident=2000+i
            offer=item(ident,f"Creatine Monohydrate family {i} 1kg",700,1000)
            offer["source_url"]=f"https://www.namaximum.cz/p/creatine-family-{i}?variant={ident}"
            products.append(offer)
        starter=item(3999,"Creatine Monohydrate starter 200g",180,200)
        starter["source_url"]="https://www.namaximum.cz/p/creatine-starter?variant=3999"
        products.append(starter)
        catalog={"merchant":"namaximum.cz","merchant_match":True,
                 "products":products}
        chosen=shortlist(catalog,BASE,SAMPLE)
        self.assertEqual(len(chosen),6)
        self.assertEqual(min(chosen,key=lambda x:x["price_czk"])["id"],"3999")
        self.assertEqual(chosen[0]["price_per_100g_powder_czk"],70)
        body=build_document(catalog,BASE,SAMPLE)["content"]
        self.assertIn("Creatine Monohydrate starter 200g",body)
        self.assertIn("Nejnižší výdaj při nákupu",body)
        self.assertIn("180,00 Kč",body)
        self.assertEqual(body.count('class="xfit-product-card"'),6)
        self.assertNotIn("nejlevnější na celém trhu",body)

    def test_insufficient_offers_stop_release(self):
        data={"merchant":"namaximum.cz","merchant_match":True,
              "products":[self.catalog["products"][0]]}
        with self.assertRaises(PublishError):
            build_document(data,BASE,SAMPLE)

    def test_purchase_links_identify_product_and_new_tab(self):
        # Synthetic fixture exercises escaping without using a live feed.
        self.catalog["products"][0]["title"] = 'Creatine Creapure "Natural" & čistý 1kg'
        links = []

        class Links(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a" and "sponsored" in attrs.get("rel", "").split():
                    links.append(attrs)

        body = build_document(self.catalog, BASE, SAMPLE)["content"]
        Links().feed(body)
        chosen = shortlist(self.catalog, BASE, SAMPLE)
        self.assertEqual(len(links), len(chosen))
        self.assertEqual(len({link["aria-label"] for link in links}), len(chosen))
        by_variant = {product["id"]: product for product in chosen}
        for link in links:
            variant = parse_qs(urlsplit(link["href"]).query)["variant"][0]
            self.assertEqual(link["aria-label"],
                "Zobrazit konkrétní balení na NaMaximum.cz: "
                + by_variant[variant]["title"] + " (nová karta)")
            self.assertEqual(link["target"], "_blank")
            self.assertIn("noopener", link["rel"].split())
            self.assertIn("nofollow", link["rel"].split())
        self.assertEqual(body.count(
            '>Zobrazit konkrétní balení na NaMaximum.cz (nová karta)</a>'), len(chosen))

    def test_prices_preserve_cents_and_explain_rank(self):
        # Synthetic fixtures: both unit prices used to display as 86 Kč.
        self.catalog["products"] = [
            item(501,"Creatine Monohydrate 500g",430.45,500),
            item(502,"Creatine Monohydrate 250g",215.10,250),
            item(503,"Creatine Pure Creapure 1kg",1100,1000),
        ]
        body=build_document(self.catalog,BASE,SAMPLE)["content"]
        self.assertIn("Cena: 215,10 Kč",body)
        self.assertIn("Cena: 430,45 Kč",body)
        self.assertIn("Cena: 1\u00a0100,00 Kč",body)
        self.assertIn("Cena za 100 g prášku: 86,04 Kč",body)
        self.assertIn("Cena za 100 g prášku: 86,09 Kč",body)
        self.assertIn("Cena za 100 g prášku: 110,00 Kč",body)
        cards=body.split('<article class="xfit-product-card"')[1:]
        self.assertEqual(len(cards),3)
        self.assertIn("Creatine Monohydrate 250g",cards[0])
        self.assertIn("Nejnižší jednotková cena ve výběru",cards[0])
        self.assertIn("Creatine Monohydrate 500g",cards[1])
