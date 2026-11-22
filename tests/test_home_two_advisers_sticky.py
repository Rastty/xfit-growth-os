"""Full-source rollback and exact public-home merchandise placement tests."""
import contextlib
import copy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_home_two_advisers_sticky as m
from scripts.wp_publish import PublishError


def guide():
    raw = ('<p>Začátečník nekupuje bez rozmyslu. '
           '<a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">'
           'Rozhodnout</a></p>' * 40)
    return {
        "id": m.GUIDE_ID, "slug": m.GUIDE_SLUG, "status": "publish",
        "link": "https://xfit.cz/" + m.GUIDE_SLUG + "/",
        "title": {"raw": "Doplňky stravy pro začátečníky: co má smysl, co nekupovat a jak se rozhodnout"},
        "content": {"raw": raw}, "excerpt":{"raw":"Rozhodnutí bez nákupu"},
        "sticky": True, "modified_gmt":"2026-11-21T14:00:00",
    }


def adviser(row):
    post_id, slug, title = row
    cards = ('<article class="xfit-product-card">'
             '<h3>NaMaximum monohydrát</h3><p>Nemusíte hned nakupovat.</p>'
             '<a data-xfit-product-id="101" '
             'href="https://www.namaximum.cz/test/">Cenu ověřit</a></article>' * 6)
    raw = '<!-- xfit-growth-os:v1 -->' + cards + ('<p>Rozhodněte se, zda nekupovat.</p>' * 85)
    assert 4000 <= len(raw) <= 150000
    return {
        "id":post_id,"slug":slug,"status":"publish",
        "link":"https://xfit.cz/" + slug + "/",
        "title":{"raw":title}, "content":{"raw":raw},
        "excerpt":{"raw":"Poradce XFIT"},
        "categories":[1], "sticky":False,
        "modified_gmt":"2026-11-21T15:00:00",
    }


def homepage(*, after=0):
    hub = "/" + m.GUIDE_SLUG + "/"
    creatine = "/" + m.ADVISERS[0][1] + "/"
    whey = "/" + m.ADVISERS[1][1] + "/"
    other = ["/extra-" + str(n) + "/" for n in range(1, 11)]
    # Before: whey is near the bottom of the first page; creatine page 2.
    paths = ([hub, "/testosteronove-boostery/", *other[:7], whey, other[7]]
             if after == 0 else
             [hub, creatine, "/testosteronove-boostery/", *other[:6], whey, *other[6:]]
             if after == 1 else
             [hub, whey, creatine, "/testosteronove-boostery/", *other])
    return '<html><main>' + ''.join(
        '<h3><a href="https://xfit.cz' + path + '">Poradce</a></h3>'
        for path in paths) + '</main></html>'


class FakeWP:
    def __init__(self):
        self.guide = guide()
        self.posts = {row[0]:adviser(row) for row in m.ADVISERS}
        self.stickies = {m.GUIDE_ID, 45}
        self.post_attempts = []

    def get_adviser(self, post_id):
        return copy.deepcopy(self.posts[post_id])

    def get_guide(self):
        return copy.deepcopy(self.guide)

    def sticky_list(self):
        return [{"id":i,"sticky":True} for i in sorted(self.stickies)]

    def home(self):
        count = len(self.stickies & set(self.posts))
        return homepage(after=count)

    def write(self, base, endpoint, *, payload):
        self.post_attempts.append((endpoint,payload))
        ident = int(endpoint.split("/")[-1])
        assert payload == {"sticky":True}
        self.posts[ident]["sticky"] = True
        self.posts[ident]["modified_gmt"] = "2026-11-22T07:31:00"
        self.stickies.add(ident)
        return {"id":ident,"status":"publish"}


class HomeTwoAdvisersTests(unittest.TestCase):
    def setup_site(self, tmp):
        f = FakeWP()
        return (
            patch.object(m,"BACKUP",Path(tmp)/"original.json"),
            patch.object(m,"get_guide",side_effect=f.get_guide),
            patch.object(m,"get_adviser",side_effect=f.get_adviser),
            patch.object(m,"sticky_list",side_effect=f.sticky_list),
            patch.object(m,"homepage_get",side_effect=f.home),
            f,
        )

    def test_exact_current_home_baseline(self):
        html = homepage()
        with patch.object(m,"homepage_get",return_value=html):
            order = m.public_order()
        self.assertEqual(m.rank(order,m.GUIDE_SLUG),1)
        self.assertEqual(m.rank(order,m.ADVISERS[1][1]),10)
        self.assertIsNone(m.rank(order,m.ADVISERS[0][1]))

    def test_backup_before_write_and_do_not_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f = self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                saved=json.loads(m.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(saved["sticky_ids_before"],[45,m.GUIDE_ID])
                self.assertEqual(saved["post_attempts"],0)
                self.assertEqual(len(saved["advisers_before"]),2)
                self.assertEqual(saved["guide_before"]["id"],m.GUIDE_ID)
                self.assertIn("namaximum",saved["advisers_before"][0]["content"]["raw"].lower())
                with self.assertRaises(PublishError):
                    m.snapshot()
            self.assertEqual(f.post_attempts,[])

    def test_two_sticky_only_posts_keep_original_source_and_home_guide_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f = self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                before=copy.deepcopy(f.posts)
                with patch.object(m,"wp_request",side_effect=f.write), \
                     patch.object(m,"normalized_base",return_value="https://xfit.cz"):
                    result=m.apply()
            self.assertEqual(result["state"],"PUBLIC_HOME_TWO_ADVISERS_TOP3_VERIFIED")
            self.assertEqual(result["creatine_adviser_rank"],3)
            self.assertEqual(result["whey_adviser_rank"],2)
            self.assertEqual(result["post_attempts"],2)
            self.assertEqual(result["post_content_changes"],0)
            self.assertEqual(result["offer_or_affiliate_link_edits"],0)
            self.assertEqual(len(f.post_attempts),2)
            self.assertEqual(f.stickies,{45,m.GUIDE_ID,25455,25456})
            for id_,original in before.items():
                self.assertEqual(m.source_without_mutable_fields(f.posts[id_]),
                                 m.source_without_mutable_fields(original))

    def test_concurrent_guide_edit_halts_before_first_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f=self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                f.guide["modified_gmt"]="2026-11-22T08:33:00"
                with patch.object(m,"wp_request",side_effect=f.write):
                    with self.assertRaises(PublishError):
                        m.apply()
            self.assertEqual(f.post_attempts,[])

    def test_another_sticky_change_halts_without_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f=self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                f.stickies.add(777)
                with patch.object(m,"wp_request",side_effect=f.write):
                    with self.assertRaises(PublishError):
                        m.apply()
            self.assertEqual(f.post_attempts,[])

    def test_public_failure_never_claims_merchandising_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f=self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                old_home=f.home
                def never_promote():
                    return homepage(after=0)
                with patch.object(m,"homepage_get",side_effect=never_promote), \
                     patch.object(m,"wp_request",side_effect=f.write), \
                     patch.object(m,"normalized_base",return_value="https://xfit.cz"):
                    with self.assertRaises(PublishError):
                        m.apply()
            # No loop that blindly repeats a write after an uncertain read.
            self.assertLessEqual(len(f.post_attempts),2)

    def test_unreviewed_source_or_missing_guide_blocks_snapshot(self):
        fake=FakeWP()
        fake.posts[25455]["content"]["raw"]="tampered"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(m,"BACKUP",Path(tmp)/"backup.json"), \
                 patch.object(m,"get_guide",side_effect=fake.get_guide), \
                 patch.object(m,"get_adviser",side_effect=fake.get_adviser):
                with self.assertRaises(PublishError):
                    m.snapshot()
                self.assertFalse(m.BACKUP.exists())
        fake=FakeWP()
        fake.guide["sticky"]=False
        with patch.object(m,"get_guide",side_effect=fake.get_guide), \
             patch.object(m,"get_adviser",side_effect=fake.get_adviser):
            with self.assertRaises(PublishError):
                m.snapshot()

    def test_manifest_rejects_missing_or_tampered_content(self):
        fake=FakeWP()
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2,p3,p4,p5,f=self.setup_site(tmp)
            with p1,p2,p3,p4,p5,contextlib.redirect_stdout(StringIO()):
                m.snapshot()
                content=json.loads(m.BACKUP.read_text(encoding="utf-8"))
                content["advisers_before"][0]["content"]["raw"]="tampered"
                with self.assertRaises(PublishError):
                    m.check_backup(content)

    def test_release_wiring_never_auto_repeats_or_bypasses_backup(self):
        path=Path(".github/workflows/xfit-home-two-advisers-sticky-onepost.yml")
        data=path.read_text(encoding="utf-8")
        self.assertIn("xfit_home_two_advisers_sticky snapshot",data)
        self.assertIn("xfit_home_two_advisers_sticky apply",data)
        self.assertLess(data.index("xfit_home_two_advisers_sticky snapshot"),
                        data.index("xfit_home_two_advisers_sticky apply"))
        self.assertIn("if-no-files-found: error",data)
        self.assertNotIn("schedule:",data)
        self.assertNotIn("workflow_dispatch:",data)


if __name__=="__main__":
    unittest.main()
