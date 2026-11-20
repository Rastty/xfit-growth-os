import unittest
from scripts.xfit_editorial_gate import check_document, EditorialError

def fixture():
    text=" ".join(["Praktická odpověď pro začátečníka vychází z dlouhodobých výsledků, složení a ověřených údajů."]*42)
    return {"content":("<h2>Jak začít</h2><p>"+text+"</p><h2>Co zkontrolovat</h2>"
    "<p>"+text.replace("začátečníka","sportovce")+"</p><h2>Časté otázky</h2>"
    "<p>"+text.replace("ověřených","veřejných")+"</p>"
    '<p><a href="https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/">Zdroj NIH</a></p>')}
class GateTests(unittest.TestCase):
    def test_quality_gate_accepts(self):
        self.assertTrue(check_document(fixture())["passed"])
    def test_short_body_rejected(self):
        with self.assertRaises(EditorialError):
            check_document({"content":"<h2>Test</h2><p>Krátké</p>"})
    def test_repeated_headings_rejected(self):
        d=fixture();d["content"]=d["content"].replace("Co zkontrolovat","Jak začít")
        with self.assertRaises(EditorialError):
            check_document(d)
    def test_cpc_affiliate_link_rejected(self):
        d=fixture();d["content"]+='<a href="https://www.namaximum.cz/p?utm_source=heureka">Produkt</a>'
        with self.assertRaises(EditorialError):
            check_document(d)
    def test_unsafe_health_claim_rejected(self):
        d=fixture();d["content"]+="<p>100% vyléčí</p>"
        with self.assertRaises(EditorialError):
            check_document(d)
    def test_unlabelled_image_rejected(self):
        d=fixture();d["content"]+='<img src="https://cdn.example/x.jpg">'
        with self.assertRaises(EditorialError):
            check_document(d)
    def test_independent_nhs_and_nice_clinical_sources_are_supported(self):
        for host in ("www.nice.org.uk", "www.rnoh.nhs.uk", "www.cuh.nhs.uk"):
            with self.subTest(host=host):
                d=fixture()
                d["content"]=d["content"].replace("ods.od.nih.gov", host)
                self.assertTrue(check_document(d)["passed"])
        d=fixture()
        d["content"]=d["content"].replace("ods.od.nih.gov", "www.nice.org.uk.invalid.example")
        with self.assertRaises(EditorialError):
            check_document(d)

    def test_rejects_full_document_embedded_in_article_content(self):
        for markup in ("<!DOCTYPE html>", "<html lang='cs'>", "<head>",
                       "<body>", "<title>Falešné SEO</title>",
                       "<meta name='description' content='wrong'>", "<base href='https://xfit.cz/'>"):
            with self.subTest(markup=markup):
                d=fixture();d["content"]+=markup
                with self.assertRaisesRegex(EditorialError,"Document-root"):
                    check_document(d)

    def test_rejects_body_canonical_even_with_valid_target(self):
        for link in ("<link rel='canonical' href='https://xfit.cz/'>",
                     '<link href="https://www.example.com/wrong" rel="alternate CANONICAL"/>'):
            with self.subTest(link=link):
                d=fixture();d["content"]+=link
                with self.assertRaisesRegex(EditorialError,"body_canonical"):
                    check_document(d)

    def test_accepts_escaped_html_tutorial_without_raw_document_tags(self):
        d=fixture()
        d["content"]+="<p>Ukázka kódu: &lt;html&gt; &lt;head&gt; &lt;link rel='canonical'&gt;.</p>"
        self.assertTrue(check_document(d)["passed"])

    def test_normal_link_and_article_semantics_remain_allowed(self):
        d=fixture();d["content"]+='''<article><header>Průvodce</header>
          <section><p>Odkaz na další web o SEO není kanonický.</p>
          <a href="https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/">Další čtení</a>
          </section><footer>Redakce</footer></article>'''
        self.assertTrue(check_document(d)["passed"])
