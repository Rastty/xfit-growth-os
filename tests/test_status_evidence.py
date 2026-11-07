"""Real production receipts, never inferred edits from green CI."""
import unittest
from urllib.request import Request

from scripts.xfit_status_evidence import (
    NoTokenRedirect, PUBLISHER_NAMES, canonical, inspect_log,
    real_release_evidence,
)
from scripts.xfit_status import render


def run(name="XFIT Whey Advisor Live", id=100, conclusion="success", status="completed"):
    return {"id": id, "name": name, "conclusion": conclusion, "status": status}


def jobs(_rid, _token):
    return {"jobs": [{"id": 501, "status": "completed", "conclusion": "success"}]}


def log_value(_job, _token):
    return (
        '2026-11-07T13:47:31Z {"state": "api_accepted", "post_id": 25456,'
        ' "slug": "xfit-os-syrovatkovy-protein-porovnani"}\n'
        '2026-11-07T13:47:32Z {"state": "live_verified", "post_id": 25456,'
        ' "url": "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",'
        ' "public_site_modified": true}\n'
    )


class StatusEvidenceTests(unittest.TestCase):
    def test_whey_github_action_logs_prove_one_real_public_update(self):
        result = real_release_evidence([run()], "fake", fetch_jobs=jobs, fetch_log=log_value)
        self.assertEqual(result["counts"], {
            "new": 0, "updated": 1, "unique_updated_pages": 1,
            "publication_or_update": 0, "unique_changed_pages": 1
        })
        self.assertEqual(result["verified_events"][0]["post_id"], 25456)
        self.assertEqual(result["verified_events"][0]["kind"], "updated")
        self.assertEqual(result["unverified_runs"], [])
        self.assertEqual(result["verified_no_change_runs"], 0)
        self.assertNotIn("api_accepted", str(result))

    def test_multiple_updates_to_two_pages_are_not_eight_different_articles(self):
        updates = []
        for idx in range(8):
            name = ("XFIT Whey Advisor Live" if idx % 2
                    else "XFIT Creatine Advisor Live")
            updates.append(run(name=name, id=500 + idx))
        def logs(job_id, token):
            raise AssertionError("Use fetch_jobs to identify each run")
        current = {"rid": 0}
        def read_jobs(rid, token):
            current["rid"] = rid
            return {"jobs":[{"id":rid,"conclusion":"success"}]}
        def read_log(jobid, token):
            if jobid % 2:
                slug,pid="xfit-os-syrovatkovy-protein-porovnani",25456
            else:
                slug,pid="xfit-os-kreatin-poradce",25455
            return (
                '{"state":"live_verified","post_id":'+str(pid)+
                ',"url":"https://xfit.cz/'+slug+
                '/","public_site_modified":true}'
            )
        output = real_release_evidence(
            updates,"fake",fetch_jobs=read_jobs,fetch_log=read_log)
        self.assertEqual(output["counts"]["updated"],8)
        self.assertEqual(output["counts"]["unique_updated_pages"],2)
        self.assertEqual(output["counts"]["unique_changed_pages"],2)
        self.assertEqual(output["counts"]["new"],0)
        report=render([],[],__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc),production=output)
        self.assertIn("aktualizační zásahy: **8** na **2** různých stránkách",report)
        self.assertEqual(report.count("nejnovější produkční doklad"),2)
        self.assertIn("aktualizace (4× v období)",report)

    def test_duplicate_receipt_not_double_counted_and_safe_link(self):
        r = run()
        info, noop = inspect_log(log_value(1, "secret") * 2, r)
        self.assertEqual(len(info), 1)
        self.assertFalse(noop)
        self.assertEqual(info[0]["url"],
                         "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/")
        self.assertNotIn("secret", str(info))

    def test_green_workflow_without_public_proof_does_not_count_as_change(self):
        result = real_release_evidence(
            [run()], "fake", fetch_jobs=jobs,
            fetch_log=lambda *_:'2026-11-07T13:48Z {"state":"api_accepted","post_id":25456}')
        self.assertEqual(len(result["verified_events"]), 0)
        self.assertEqual(len(result["unverified_runs"]), 1)
        self.assertEqual(result["verified_no_change_runs"], 0)

    def test_known_noop_and_no_more_targets_do_not_claim_new_posts(self):
        for label, value in [
            ("XFIT Autonomous Approved Editorial Publish",
             '{"status":"ALL_PINNED_ARTICLES_PUBLIC_VERIFIED","new_posts":0,"verified_articles":1}'),
            ("XFIT AI Author and Source-Bound Live Publisher",
             '{"status":"NO_APPROVED_TARGET"}')
        ]:
            with self.subTest(label=label):
                result = real_release_evidence([run(name=label)], "fake",
                                               fetch_jobs=jobs, fetch_log=lambda *_:value)
                self.assertEqual(result["counts"]["new"], 0)
                self.assertEqual(result["verified_no_change_runs"], 1)
                self.assertEqual(result["unverified_runs"], [])

    def test_constrained_explicit_new_post_is_counted(self):
        label = "XFIT Autonomous Approved Editorial Publish"
        value = (
            '{"status":"PUBLIC_VERIFIED_NEW_POST","post_id":25542,'
            '"slug":"xfit-os-porovnani-proteinove-tycinky","new_posts":1,'
            '"url":"https://xfit.cz/xfit-os-porovnani-proteinove-tycinky/"}'
        )
        result = real_release_evidence([run(name=label)],"fake",
                                       fetch_jobs=jobs,fetch_log=lambda *_:value)
        self.assertEqual(result["counts"]["new"],1)
        self.assertEqual(result["counts"]["updated"],0)

    def test_legacy_editor_stage_is_genuine_update(self):
        label="XFIT Protein Intake Editorial Upgrade"
        value=('2026-11-07T13:50:00Z {"stage":"live_verified",'
               '"post_id":13717,"url":"https://xfit.cz/kolik-bilkovin-pruvodce/"}')
        res=real_release_evidence([run(name=label)],"fake",
                                  fetch_jobs=jobs,fetch_log=lambda *_:value)
        self.assertEqual(res["counts"]["updated"],1)

    def test_unknown_failures_and_inaccessible_logs_are_not_zero_progress(self):
        sample=[
            run(conclusion="failure",id=10),
            run(conclusion="success",id=11),
        ]
        def fail(*_):
            raise OSError("secret=NEVER_PRINT_THIS")
        result=real_release_evidence(sample,"fake",fetch_jobs=jobs,fetch_log=fail)
        self.assertEqual(len(result["unverified_runs"]),2)
        self.assertEqual(result["counts"]["new"],0)
        self.assertNotIn("NEVER_PRINT_THIS",str(result))

    def test_non_publish_jobs_are_not_edits(self):
        result=real_release_evidence([run(name="XFIT Code Checks")],
                                     "fake",fetch_jobs=jobs,fetch_log=log_value)
        self.assertEqual(result["publisher_runs_seen"],0)
        self.assertEqual(result["unverified_runs"],[])

    def test_reject_noncanonical_unsafe_and_wrong_pinned_owner_receipts(self):
        slug="xfit-os-syrovatkovy-protein-porovnani"
        for url, pid in [
            ("https://attacker.example/"+slug+"/",25456),
            ("http://xfit.cz/"+slug+"/",25456),
            ("https://xfit.cz/"+slug+"/?a_aid=hidden",25456),
            ("https://xfit.cz/"+slug+"/",999),
            ("https://xfit.cz:8443/"+slug+"/",25456),
            ("https://xfit.cz/"+slug+"/#notcanonical",25456),
        ]:
            with self.subTest(url=url,pid=pid):
                self.assertIsNone(canonical(slug,url,pid))
        self.assertIsNone(canonical("../admin","https://xfit.cz/../admin/",25456))

    def test_bearer_token_not_forwarded_to_signed_download(self):
        request=Request("https://api.github.com/repos/Rastty/xfit-growth-os/actions/jobs/1/logs",
                        headers={"Authorization":"Bearer SECRET","Accept":"application/json"})
        new=NoTokenRedirect().redirect_request(
            request, None, 302, "Found", {},
            "https://pipelines.actions.githubusercontent.com/final-signed")
        self.assertNotIn("Authorization",new.headers)
        self.assertEqual(new.get_header("Accept"),"application/json")
        with self.assertRaises(ValueError):
            NoTokenRedirect().redirect_request(
                request,None,302,"Found",{},"http://untrusted.example/log")

    def test_owner_report_distinguishes_real_zero_and_unverified(self):
        labels=[(2,"UX a poradci","připravené zadání","https://github.com/Rastty/xfit-growth-os/issues/2")]
        result=real_release_evidence([run()], "fake",fetch_jobs=jobs,fetch_log=log_value)
        body=render([run()], [("Syrovátkový protein","publikováno ve WP REST",
                               "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/")],
                    __import__("datetime").datetime(2026,11,7,tzinfo=__import__("datetime").timezone.utc),
                    labels,result)
        self.assertIn("Nové články: **0**; ověřené aktualizační zásahy: **1** na **1** různých stránkách",body)
        self.assertIn("produkční doklad",body)
        self.assertNotIn("NEOVĚŘENO:",body)
        result=real_release_evidence([run()],"fake",fetch_jobs=jobs,
                                     fetch_log=lambda *_: '{"state":"api_accepted"}')
        text=render([],[],__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc),production=result)
        self.assertIn("**NEOVĚŘENO: 1 publikačních běhů.**",text)
        self.assertIn("nelze tvrdit, že bylo provedeno 0 změn",text)


if __name__=="__main__":
    unittest.main()
