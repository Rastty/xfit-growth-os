"""Tests for exact allowlist-only legacy evidence handoffs; never reach WordPress."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_verified_inlink_release as release
from scripts.wp_publish import PublishError

CFG = release.ALLOWLIST["creatine_safety_2139"]


def post(*, body=None, post_id=CFG.post_id, slug=CFG.slug,
         status="publish", link=None, modified="2026-11-09T16:00:00"):
    if body is None:
        body=("<h2>Bezpečnost kreatinu</h2>" +
              "<p>Jaké jsou bezpečnostní otázky kreatinu a jeho užívání?</p>"*50)
    return {
        "id":post_id,"slug":slug,"status":status,
        "link":link or CFG.url,
        "title":{"raw":"Kreatin monohydrát a bezpečnostní rizika"},
        "content":{"raw":body},"modified_gmt":modified,
    }


class VerifiedInlinkTests(unittest.TestCase):
    def test_allowlist_contains_only_exact_safety_post(self):
        self.assertEqual(set(release.ALLOWLIST),{"creatine_safety_2139","creatine_price_10835"})
        self.assertEqual(CFG.post_id,2139)
        self.assertEqual(CFG.target,
                         "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/")
        self.assertNotIn("namaximum",CFG.paragraph.casefold())
        self.assertNotIn("affil",CFG.paragraph.casefold())
        self.assertIn("lékařem",CFG.paragraph)

    def test_exact_append_preserves_all_source_elements(self):
        p=post()
        state=release.prepare(CFG,p)
        self.assertEqual(state["mode"],"update")
        self.assertTrue(state["after"].startswith(state["before"]+"\n"))
        self.assertEqual(state["after"].count(CFG.marker),1)
        self.assertEqual(state["after"].count(CFG.target),1)
        self.assertIn(CFG.target,release.real_links(state["after"]))
        self.assertNotIn(CFG.target,release.real_links(state["before"]))
        self.assertEqual(state["hash"],release.digest(p["content"]["raw"]))

    def test_existing_link_is_never_duplicated(self):
        edited=release.prepare(CFG,post())["after"]
        result=release.prepare(CFG,post(body=edited))
        self.assertEqual(result["mode"],"already_linked")
        self.assertEqual(result["after"],edited)

    def test_plain_text_url_is_not_real_anchor(self):
        old=post()
        old["content"]["raw"]+="<p>"+CFG.target+"</p>"
        self.assertEqual(release.prepare(CFG,old)["mode"],"update")

    def test_guard_rejects_identity_drift_and_partial_patch(self):
        original=post()
        for change in (
            {"id":1111},
            {"slug":"other"},
            {"status":"draft"},
            {"link":"https://other.example/"+CFG.slug+"/"},
            {"title":{"raw":"Completely unrelated article"}},
            {"modified_gmt":""},
            {"content":{"raw":"short"}},
            {"content":{"raw":original["content"]["raw"]+CFG.marker}},
        ):
            with self.subTest(change=change):
                p=post()
                p.update(change)
                with self.assertRaises(PublishError):
                    release.prepare(CFG,p)

    def test_public_check_requires_real_anchor_and_unique_guidance(self):
        self.assertTrue(release.public_verified(CFG,reader=lambda _:CFG.paragraph))
        self.assertFalse(release.public_verified(CFG,reader=lambda _:CFG.paragraph.replace(
            'href="'+CFG.target+'"','href="https://xfit.cz/somewhere-else/"'
        )))
        self.assertFalse(release.public_verified(CFG,reader=lambda _:CFG.paragraph.replace(
            CFG.sentence,"Jiné téma"
        )))

    def test_snapshot_is_real_backup_before_exactly_one_post(self):
        old=post()
        new=post(body=release.prepare(CFG,old)["after"],
                 modified="2026-11-09T16:01:00")
        with tempfile.TemporaryDirectory() as folder, patch.object(
                release.Handoff,"backup",property(lambda self:Path(folder)/"b.json")):
            with patch.object(release,"remote",return_value=old):
                release.snapshot(CFG)
            saved=json.loads(CFG.backup.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],old["content"]["raw"])
            self.assertEqual(saved["remote_writes"],0)
            with patch.object(release,"remote",side_effect=[old,new]), \
                 patch.object(release,"normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(release,"wp_request",
                              return_value={"id":CFG.post_id,"status":"publish"}) as writer, \
                 patch.object(release,"public_verified",return_value=True) as public:
                release.apply(CFG)
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"],
                             {"content":new["content"]["raw"]})
            public.assert_called_once_with(CFG)

    def test_after_snapshot_source_drift_blocks_write(self):
        old=post()
        drifted=post(body=old["content"]["raw"]+"<p>Additional editor update.</p>")
        with tempfile.TemporaryDirectory() as folder, patch.object(
                release.Handoff,"backup",property(lambda self:Path(folder)/"b.json")):
            with patch.object(release,"remote",return_value=old):
                release.snapshot(CFG)
            with patch.object(release,"remote",return_value=drifted), \
                 patch.object(release,"wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply(CFG)
            writer.assert_not_called()


PRICE = release.ALLOWLIST["creatine_price_10835"]


def price_post(*, body=None, title="Kde koupit nejlevnější kreatin pro fitness?",
               modified="2026-11-09T20:00:00"):
    if body is None:
        body = ("<h2>Nejlevnější kreatin pro fitness</h2>"
                + "<p>Užitečný a původní obsah srovnání ceny a balení.</p>" * 55)
    return {
        "id": 10835, "slug": PRICE.slug, "status": "publish",
        "link": PRICE.url, "title": {"raw": title},
        "content": {"raw": body}, "modified_gmt": modified,
    }


class PriceHandoffTests(unittest.TestCase):
    def test_exact_allowlist_and_helpful_content(self):
        self.assertEqual(PRICE.post_id, 10835)
        self.assertEqual(PRICE.slug,"kde-koupit-nejlevnejsi-kreatin-pro-fitness")
        self.assertEqual(PRICE.target,"https://xfit.cz/xfit-os-kreatin-poradce/")
        self.assertEqual(PRICE.paragraph.count(PRICE.target),1)
        self.assertIn("dopravy",PRICE.paragraph)
        self.assertIn("nekupujte jej",PRICE.paragraph)
        self.assertIn("nejnižší ceny na celém trhu",PRICE.paragraph)
        self.assertNotIn("a_aid",PRICE.paragraph)
        self.assertNotIn("namaximum",PRICE.paragraph.casefold())

    def test_preserves_legacy_source_and_never_repeats_anchor(self):
        old=price_post()
        state=release.prepare(PRICE,old)
        self.assertEqual(state["mode"],"update")
        self.assertEqual(state["after"],state["before"]+"\n"+PRICE.paragraph)
        self.assertIn(PRICE.target,release.real_links(state["after"]))
        self.assertTrue(release.public_verified(PRICE,reader=lambda _:PRICE.paragraph))
        done=price_post(body=state["after"])
        self.assertEqual(release.prepare(PRICE,done)["mode"],"already_linked")

    def test_identity_and_race_guards_block_unreviewed_mutation(self):
        for changed in (
            {"id":10836}, {"status":"draft"}, {"slug":"wrong"},
            {"title":{"raw":"Zcela nesouvisející článek"}},
            {"link":"https://xfit.cz/other-page/"},
        ):
            with self.subTest(changed=changed):
                item=price_post()
                item.update(changed)
                with self.assertRaises(PublishError):
                    release.prepare(PRICE,item)
        original=price_post()
        with tempfile.TemporaryDirectory() as folder, patch.object(
                release.Handoff,"backup",property(lambda self:Path(folder)/"b.json")):
            with patch.object(release,"remote",return_value=original):
                release.snapshot(PRICE)
            changed=price_post(body=original["content"]["raw"]+"<p>New editor update.</p>")
            with patch.object(release,"remote",return_value=changed), \
                 patch.object(release,"wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply(PRICE)
            writer.assert_not_called()

    def test_precise_onepost_write_and_public_readback_with_full_backup(self):
        old=price_post()
        updated=release.prepare(PRICE,old)["after"]
        new=price_post(body=updated,modified="2026-11-09T20:01:00")
        with tempfile.TemporaryDirectory() as folder, patch.object(
                release.Handoff,"backup",property(lambda self:Path(folder)/"b.json")):
            with patch.object(release,"remote",return_value=old):
                release.snapshot(PRICE)
            backup=json.loads(PRICE.backup.read_text(encoding="utf-8"))
            self.assertEqual(backup["original_raw"],old["content"]["raw"])
            self.assertEqual(backup["remote_writes"],0)
            with patch.object(release,"remote",side_effect=[old,new]), \
                 patch.object(release,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(release,"wp_request",return_value={"id":10835,"status":"publish"}) as writer, \
                 patch.object(release,"public_verified",return_value=True) as public:
                release.apply(PRICE)
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"],{"content":updated})
            public.assert_called_once_with(PRICE)


if __name__=="__main__":
    unittest.main()
