"""Real production receipts, never inferred edits from green CI."""
import json
import unittest
from urllib.request import Request

from scripts.xfit_status_evidence import (
    NoTokenRedirect, PUBLISHER_NAMES, canonical, inspect_log,
    coupon_cleanup_evidence, real_release_evidence,
    PLANT_FIRST, PLANT_DAILY, PLANT_HANDOFF,
    EQUIPMENT_FIRST, EQUIPMENT_DAILY, EQUIPMENT_HANDOFFS, ROUTE_RELEASES,
    CREATINE_LEGACY_NAME, CREATINE_LEGACY_TARGETS, CREATINE_LEGACY_STEPS,
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

    def test_pilates_title_release_counted_only_after_real_apply(self):
        run_name = "XFIT Pilates GSC Query-Intent Title Onepost"
        receipt = (
            '{"state":"PUBLIC_VERIFIED","post_id":3660,"posts_changed":1,'
            '"post_attempts":1,"title_changed":true,'
            '"existing_html_preserved":true,"public_site_modified":true,'
            '"new_posts":0,"deletes":0,"redirects":0,'
            '"url":"https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/"}'
        )
        nl = chr(10)
        actual_apply = nl.join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_pilates_gsc_title_release apply | tee -a \"$GITHUB_STEP_SUMMARY\"",
            "##[endgroup]",
        )) + nl
        evidence = real_release_evidence(
            [run(name=run_name, id=42470689675)], "fake",
            fetch_jobs=jobs,
            fetch_log=lambda *_: receipt + nl + actual_apply + receipt)
        self.assertEqual(evidence["counts"]["updated"], 1)
        self.assertEqual(evidence["counts"]["unique_changed_pages"], 1)
        self.assertEqual(evidence["verified_events"][0]["post_id"], 3660)
        self.assertEqual(evidence["unverified_runs"], [])
        # Test fixtures always emit a fake successful POST before actual apply.
        wrong = (
            receipt, actual_apply,
            receipt + nl + actual_apply + receipt.replace('"post_id":3660', '"post_id":3661'),
            receipt + nl + actual_apply + receipt.replace('"posts_changed":1', '"posts_changed":2'),
            receipt + nl + actual_apply + receipt.replace('"existing_html_preserved":true', '"existing_html_preserved":false'),
            receipt + nl + actual_apply + receipt.replace('"title_changed":true', '"title_changed":false'),
            receipt + nl + actual_apply + receipt.replace('"public_site_modified":true', '"public_site_modified":false'),
            receipt + nl + actual_apply + receipt.replace('"new_posts":0', '"new_posts":1'),
            receipt + nl + actual_apply + receipt.replace('jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates', 'jinak-nazvany-clanek'),
        )
        for log_text in wrong:
            with self.subTest(probe=log_text[-80:]):
                unverified = real_release_evidence(
                    [run(name=run_name, id=42470689675)], "fake",
                    fetch_jobs=jobs, fetch_log=lambda *_: log_text)
                self.assertEqual(unverified["counts"]["updated"], 0)
                self.assertEqual(len(unverified["unverified_runs"]), 1)

    def test_pilates_noop_is_not_a_second_edit(self):
        name = "XFIT Pilates GSC Query-Intent Title Onepost"
        marker = "\n".join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_pilates_gsc_title_release apply",
            "##[endgroup]",
        )) + "\n"
        nochange = real_release_evidence(
            [run(name=name, id=42470689675)], "fake",
            fetch_jobs=jobs,
            fetch_log=lambda *_: marker +
                '{"state":"ALREADY_APPLIED_NO_WRITE","post_id":3660,'
                '"post_attempts":0,"public_site_modified":false}')
        self.assertEqual(nochange["counts"]["updated"], 0)
        self.assertEqual(nochange["verified_no_change_runs"], 1)

    def test_11595_verified_after_actual_apply_only(self):
        name = "XFIT Coupon Post 11595 Recovery"
        actual = ('{"state":"PUBLIC_VERIFIED","post_id":11595,'
                  '"url":"https://xfit.cz/nove-trendy-v-tekutem-spalovaci-tuku-pro-fitness-nadsence/",'
                  '"shortcodes_removed":3,"posts_changed":1,"post_attempts":1,'
                  '"public_site_modified":true,"deletes":0,"redirects":0}')
        nl = chr(10)
        step = nl.join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_coupon_recovery_11595 apply",
            "##[endgroup]",
        )) + nl
        result = real_release_evidence(
            [run(name=name, id=42467009202)], "fake",
            fetch_jobs=jobs,
            fetch_log=lambda *_: actual + nl + step + actual)
        self.assertEqual(result["counts"]["updated"], 1)
        self.assertEqual(result["counts"]["unique_changed_pages"], 1)
        self.assertEqual(result["verified_events"][0]["post_id"], 11595)
        self.assertEqual(result["verified_no_change_runs"], 0)

        invalid = (
            actual,
            step,
            actual + nl + step + actual.replace('"post_id":11595', '"post_id":11600'),
            actual + nl + step + actual.replace('"shortcodes_removed":3', '"shortcodes_removed":2'),
            actual + nl + step + actual.replace('nove-trendy-v-tekutem-spalovaci-tuku-pro-fitness-nadsence',
                                                   'jinak-nazvany-clanek'),
            actual + nl + step + actual.replace('"public_site_modified":true',
                                                   '"public_site_modified":false'),
            actual + nl + step + actual.replace('"posts_changed":1', '"posts_changed":2'),
        )
        for fake in invalid:
            with self.subTest(log=fake[-100:]):
                check = real_release_evidence(
                    [run(name=name, id=42467009202)], "fake",
                    fetch_jobs=jobs, fetch_log=lambda *_: fake)
                self.assertEqual(check["counts"]["updated"], 0)
                self.assertEqual(len(check["unverified_runs"]), 1)

    def test_11595_noop_after_apply_is_not_a_new_change(self):
        name = "XFIT Coupon Post 11595 Recovery"
        marker = chr(10).join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_coupon_recovery_11595 apply",
            "##[endgroup]",
        )) + chr(10)
        no_op = real_release_evidence(
            [run(name=name, id=42467009202)], "fake",
            fetch_jobs=jobs,
            fetch_log=lambda *_: marker +
                '{"state":"ALREADY_CLEAN_NO_WRITE","post_id":11595,'
                '"shortcodes_removed":0,"public_site_modified":false}')
        self.assertEqual(no_op["counts"]["updated"], 0)
        self.assertEqual(no_op["verified_no_change_runs"], 1)

    def test_coupon_production_receipt_requires_real_post_backup_and_apply_step(self):
        coupon_run=run(name="XFIT Coupon Post 11600 Recovery",id=42458541415)
        actual=('{"state":"PUBLIC_VERIFIED","post_id":11600,'
                '"url":"https://xfit.cz/test-a-recenze-nejlepsich-tekutych-spalovacu-tuku-pro-fitnesscviky/",'
                '"shortcodes_removed":3,"posts_changed":1,"post_attempts":1,'
                '"public_site_modified":true,"deletes":0,"redirects":0}')
        # The real logs contain a synthetic success from source tests before
        # the actual guarded apply step; that earlier value never counts.
        nl=chr(10)
        shell=nl.join((
            "2026-11-08T07:22:47Z ##[group]Run set -o pipefail",
            "2026-11-08T07:22:47Z python -m scripts.xfit_coupon_recovery apply",
            "2026-11-08T07:22:47Z ##[endgroup]",
        ))+nl
        good_log=fake=actual
        good_log=fake+nl+shell+"2026-11-08T07:22:54Z "+actual
        result=real_release_evidence(
            [coupon_run],"fake",fetch_jobs=jobs,fetch_log=lambda *_:good_log)
        self.assertEqual(result["counts"]["updated"],1)
        self.assertEqual(result["counts"]["unique_updated_pages"],1)
        self.assertEqual(result["counts"]["new"],0)
        self.assertEqual(result["verified_events"][0]["post_id"],11600)
        self.assertEqual(result["unverified_runs"],[])

        for bad_log in (
            fake,
            shell,
            fake+nl+shell+fake.replace('"post_id":11600','"post_id":11888'),
            fake+nl+shell+fake.replace('"shortcodes_removed":3','"shortcodes_removed":1'),
            fake+nl+shell+fake.replace('"public_site_modified":true','"public_site_modified":false'),
        ):
            with self.subTest(bad_log=bad_log[-90:]):
                found=real_release_evidence(
                    [coupon_run],"fake",fetch_jobs=jobs,
                    fetch_log=lambda *_:bad_log)
                self.assertEqual(found["counts"]["updated"],0)
                self.assertEqual(len(found["unverified_runs"]),1)

    def test_verified_coupon_noop_counts_as_nochange_not_a_new_post(self):
        nl=chr(10)
        shell=nl.join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_coupon_recovery apply",
            "##[endgroup]",
        ))+nl
        out=real_release_evidence(
            [run(name="XFIT Coupon Post 11600 Recovery")],"fake",
            fetch_jobs=jobs,
            fetch_log=lambda *_:shell+
                '{"state":"ALREADY_CLEAN_NO_WRITE","post_id":11600,'
                '"shortcodes_removed":0,"public_site_modified":false}')
        self.assertEqual(out["counts"]["updated"],0)
        self.assertEqual(out["verified_no_change_runs"],1)

    def test_real_protein_pack_update_only_after_apply_step(self):
        name="XFIT Protein Pack-use One-post Live Release"
        release=run(name=name,id=42460661426)
        good=('{"state":"PUBLIC_VERIFIED","post_id":25451,'
              '"slug":"xfit-os-protein-guide",'
              '"url":"https://xfit.cz/xfit-os-protein-guide/",'
              '"old_paragraphs_replaced":1,"posts_changed":1,'
              '"post_attempts":1,"new_posts":0,"deletes":0,"redirects":0,'
              '"public_site_modified":true}')
        nl=chr(10)
        marker=nl.join((
            "2026-11-08T07:54:27Z ##[group]Run set -o pipefail",
            "2026-11-08T07:54:27Z python -m scripts.xfit_protein_pack_release apply",
            "2026-11-08T07:54:27Z ##[endgroup]",
        ))+nl
        actual_log=good+nl+marker+"2026-11-08T07:54:28Z "+good
        out=real_release_evidence(
            [release],"fake",fetch_jobs=jobs,
            fetch_log=lambda *_:actual_log)
        self.assertEqual(out["counts"]["new"],0)
        self.assertEqual(out["counts"]["updated"],1)
        self.assertEqual(out["counts"]["unique_updated_pages"],1)
        self.assertEqual(out["verified_events"][0]["post_id"],25451)
        self.assertNotIn("UNRESOLVED",str(out))
        for bad_log in (
            good,
            marker,
            good+nl+marker+good.replace('"post_id":25451','"post_id":25456'),
            good+nl+marker+good.replace('"new_posts":0','"new_posts":1'),
            good+nl+marker+good.replace('"old_paragraphs_replaced":1',
                                      '"old_paragraphs_replaced":2'),
            good+nl+marker+good.replace('"public_site_modified":true',
                                      '"public_site_modified":false'),
        ):
            with self.subTest(log_tail=bad_log[-100:]):
                invalid=real_release_evidence(
                    [release],"fake",fetch_jobs=jobs,
                    fetch_log=lambda *_:bad_log)
                self.assertEqual(invalid["counts"]["updated"],0)
                self.assertEqual(len(invalid["unverified_runs"]),1)

    def test_already_applied_protein_is_noop(self):
        marker=chr(10).join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_protein_pack_release apply",
            "##[endgroup]",
        ))+chr(10)
        out=real_release_evidence(
            [run(name="XFIT Protein Pack-use One-post Live Release")],
            "fake",fetch_jobs=jobs,fetch_log=lambda *_:marker+
            '{"state":"ALREADY_APPLIED_NO_WRITE","post_id":25451,'
            '"post_attempts":0,"public_site_modified":false}')
        self.assertEqual(out["counts"]["updated"],0)
        self.assertEqual(out["verified_no_change_runs"],1)

    def test_real_beginner_goal_release_counts_only_actual_apply(self):
        name="XFIT Beginner Goal Handoffs One-post Live"
        release=run(name=name,id=42464009001)
        actual=('{"state":"PUBLIC_VERIFIED","post_id":25458,'
                '"slug":"xfit-os-doplnky-pro-zacatecniky",'
                '"url":"https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",'
                '"posts_changed":1,"new_posts":0,"post_attempts":1,'
                '"new_goal_links":4,"open_no_buy_answer":true,'
                '"public_site_modified":true,"deletes":0,"redirects":0}')
        nl=chr(10)
        marker=nl.join((
            "2026-11-08T08:41:51Z ##[group]Run set -o pipefail",
            "2026-11-08T08:41:51Z python -m scripts.xfit_beginner_goal_release apply",
            "2026-11-08T08:41:51Z ##[endgroup]",
        ))+nl
        # Unit tests printed a synthetic copy BEFORE the real apply.
        actual_log=actual+nl+marker+"2026-11-08T08:41:57Z "+actual
        result=real_release_evidence(
            [release],"fake",fetch_jobs=jobs,fetch_log=lambda *_:actual_log)
        self.assertEqual(result["counts"]["updated"],1)
        self.assertEqual(result["counts"]["unique_updated_pages"],1)
        self.assertEqual(result["counts"]["new"],0)
        self.assertEqual(result["verified_events"][0]["post_id"],25458)
        self.assertEqual(result["unverified_runs"],[])
        for wrong in (
            actual,
            marker,
            actual+nl+marker+actual.replace('"post_id":25458','"post_id":25451'),
            actual+nl+marker+actual.replace('"new_goal_links":4','"new_goal_links":3'),
            actual+nl+marker+actual.replace('"open_no_buy_answer":true','"open_no_buy_answer":false'),
            actual+nl+marker+actual.replace('"public_site_modified":true','"public_site_modified":false'),
        ):
            with self.subTest(wrong=wrong[-100:]):
                observed=real_release_evidence(
                    [release],"fake",fetch_jobs=jobs,fetch_log=lambda *_:wrong)
                self.assertEqual(observed["counts"]["updated"],0)
                self.assertEqual(len(observed["unverified_runs"]),1)

    def test_beginner_already_applied_is_zero_new_edits(self):
        name="XFIT Beginner Goal Handoffs One-post Live"
        marker=chr(10).join((
            "##[group]Run set -o pipefail",
            "python -m scripts.xfit_beginner_goal_release apply",
            "##[endgroup]",
        ))+chr(10)
        out=real_release_evidence(
            [run(name=name)],"fake",fetch_jobs=jobs,
            fetch_log=lambda *_:marker+
                '{"state":"ALREADY_APPLIED_NO_WRITE","post_id":25458,'
                '"public_site_modified":false,"post_attempts":0}')
        self.assertEqual(out["counts"]["updated"],0)
        self.assertEqual(out["verified_no_change_runs"],1)

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



def coupon_run(rid=46017000248, conclusion="failure"):
    return run(name="XFIT Expired Coupon Cleanup", id=rid, conclusion=conclusion)


def coupon_job(conclusion="failure", *, backup="success"):
    steps = [
        ("Repository tests", "success"),
        ("Read-only paginated preview of up to eight never-attempted coupon posts", "success"),
        ("Backup artifact is mandatory before any WordPress writes", backup),
        ("Reserve all post IDs in issue 363 BEFORE any WP POST; then verify public pages", conclusion),
    ]
    return {"jobs": [{"id": 501, "name": "cleanup", "status": "completed",
                      "conclusion": conclusion, "steps": [
                          {"name": name, "status": "completed", "conclusion": result}
                          for name, result in steps]}]}


def coupon_receipt():
    return {
        "state": "coupon_wave_partial", "posts_changed": 7, "shortcodes_removed": 21,
        "unchanged_failures": [{"id": 10409, "stage": "write_request", "state": "unchanged"}],
        "uncertain_posts": [],
        "public_verified_post_ids": [10418, 10412, 10406, 10402, 10398, 10396, 10392],
        "public_not_verified": [], "deletes": 0, "redirects": 0,
    }


def coupon_log(final=None, *, reservation=None):
    if final is None:
        final = coupon_receipt()
    if reservation is None:
        reservation = {"state": "COUPON_ATTEMPTS_RESERVED_BEFORE_WP", "issue": 363,
                       "new_attempt_ids": 8, "total_attempts": 126, "wordpress_writes": 0}
    # A fixture identical to the real result printed by tests BEFORE apply
    # must not be counted, even when the real step is missing.
    return "\n".join((
        json.dumps(final),
        "2026-11-27T14:33:46Z ##[group]Run set -o pipefail",
        'python -m scripts.xfit_coupon_cleanup apply | tee -a "$GITHUB_STEP_SUMMARY"',
        "2026-11-27T14:33:46Z ##[endgroup]",
        json.dumps(reservation),
        json.dumps(final),
    ))


class CouponStatusEvidenceTests(unittest.TestCase):
    def collect(self, log=None, *, conclusion="failure", job=None):
        return real_release_evidence(
            [coupon_run(conclusion=conclusion)], "fake",
            fetch_jobs=lambda *_: job if job is not None else coupon_job(conclusion),
            fetch_log=lambda *_: coupon_log() if log is None else log)

    def test_partial_wave_counts_only_public_ids_and_keeps_canonical_counts_separate(self):
        output = self.collect()
        proof = output["coupon_cleanup"]
        self.assertEqual(proof["public_verified_unique_posts"], 7)
        self.assertEqual(proof["public_verified_update_events"], 7)
        self.assertEqual(proof["known_public_verified_shortcodes"], 21)
        self.assertFalse(proof["shortcode_count_incomplete"])
        self.assertEqual(proof["waves"][0]["unchanged_post_ids"], [10409])
        self.assertEqual(proof["unknown_run_ids"], [])
        self.assertEqual(output["counts"]["updated"], 0)
        self.assertEqual(output["counts"]["new"], 0)
        body = render([coupon_run()], [], __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc), production=output)
        self.assertIn("**7/8** veřejně ověřeno", body)
        self.assertIn("nezměněné 1", body)
        self.assertIn("kuponů (včetně částečných dávek)", body)
        self.assertIn("doložené odstraněné shortcode bloky: **21**", body)
        self.assertNotIn("nebyl zaznamenán žádný schválený publikační běh", body)

    def test_complete_wave_and_public_subset_have_distinct_shortcode_proof(self):
        final = coupon_receipt()
        final.update(state="coupon_wave_verified", posts_changed=8, shortcodes_removed=24,
                     unchanged_failures=[])
        final["public_verified_post_ids"].append(10409)
        complete = self.collect(coupon_log(final), conclusion="success")["coupon_cleanup"]
        self.assertEqual(complete["public_verified_unique_posts"], 8)
        self.assertEqual(complete["known_public_verified_shortcodes"], 24)
        final["state"] = "coupon_wave_public_unverified"
        final["public_verified_post_ids"].remove(10409)
        final["public_not_verified"] = [{"id": 10409, "state": "EXPIRED_COUPON_VISIBLE"}]
        partial = self.collect(coupon_log(final))["coupon_cleanup"]
        self.assertEqual(partial["public_verified_unique_posts"], 7)
        self.assertEqual(partial["known_public_verified_shortcodes"], 0)
        self.assertTrue(partial["shortcode_count_incomplete"])
        self.assertEqual(partial["waves"][0]["public_unverified_post_ids"], [10409])

    def test_malformed_wrong_step_or_backup_cannot_become_proof(self):
        final = coupon_receipt()
        bad_logs = [json.dumps(final), coupon_log().replace(
            "scripts.xfit_coupon_cleanup apply", "scripts.fake apply"),
            coupon_log().replace('"issue": 363', '"issue": 1'),
            coupon_log().replace('"wordpress_writes": 0', '"wordpress_writes": 8'),
            coupon_log().replace('"new_attempt_ids": 8', '"new_attempt_ids": 7')]
        for patch in (
            {"posts_changed": 8}, {"shortcodes_removed": 1}, {"deletes": 1},
            {"public_verified_post_ids": [10418] * 7},
            {"public_verified_post_ids": [10409, 10412, 10406, 10402, 10398, 10396, 10392]},
            {"state": "coupon_wave_verified"}, {"uncertain_posts": [{"id": 99999}]},
            {"unchanged_failures": [10409]},
            {"public_verified_post_ids": [True, 10412, 10406, 10402, 10398, 10396, 10392]},
        ):
            bad_logs.append(coupon_log(dict(final, **patch)))
        for log in bad_logs:
            with self.subTest(log=log[-100:]):
                proof = self.collect(log)["coupon_cleanup"]
                self.assertEqual(proof["public_verified_unique_posts"], 0)
                self.assertEqual(proof["unknown_run_ids"], [46017000248])
                self.assertTrue(proof["shortcode_count_incomplete"])
        proof = self.collect(job=coupon_job(backup="failure"))["coupon_cleanup"]
        self.assertEqual(proof["public_verified_unique_posts"], 0)
        self.assertEqual(proof["unknown_run_ids"], [46017000248])

    def test_uncertain_write_keeps_verified_subset_and_marks_total_incomplete(self):
        final = coupon_receipt()
        final["unchanged_failures"] = []
        final["uncertain_posts"] = [{"id": 10409, "state": "readback_unavailable"}]
        proof = self.collect(coupon_log(final))["coupon_cleanup"]
        self.assertEqual(proof["public_verified_unique_posts"], 7)
        self.assertEqual(proof["known_public_verified_shortcodes"], 21)
        self.assertTrue(proof["shortcode_count_incomplete"])
        self.assertEqual(proof["waves"][0]["uncertain_post_ids"], [10409])

    def test_duplicate_run_inventory_does_not_double_count(self):
        proof = coupon_cleanup_evidence(
            [coupon_run(), coupon_run()], "fake", fetch_jobs=lambda *_: coupon_job(),
            fetch_log=lambda *_: coupon_log())
        self.assertEqual(len(proof["waves"]), 1)
        self.assertEqual(proof["public_verified_unique_posts"], 7)
        self.assertEqual(proof["known_public_verified_shortcodes"], 21)

class PlantProductionProofTests(unittest.TestCase):
    def evidence(self, name, receipt, browser, *, marker=None):
        mark = marker or {
            PLANT_FIRST: "##[group]Run python -m scripts.xfit_plant_comparison apply",
            PLANT_DAILY: "##[group]Run python -m scripts.xfit_plant_refresh apply",
            PLANT_HANDOFF: "##[group]Run set -o pipefail\npython -m scripts.xfit_verified_inlink_release beginner_plant_commerce_25458 apply",
        }[name]
        log = "\n".join((json.dumps(receipt), mark, "##[endgroup]", json.dumps(receipt), json.dumps(browser)))
        return real_release_evidence([run(name=name)], "fake", fetch_jobs=jobs,
                                     fetch_log=lambda *_: log)

    def test_initial_release_requires_exact_new_id_and_mobile_proof(self):
        receipt = {"state": "PUBLIC_VERIFIED_NEW_POST", "post_id": 26152,
                   "slug": "xfit-os-rostlinne-proteiny-porovnani",
                   "url": "https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/",
                   "new_posts": 1, "public_site_modified": True}
        browser = {"state": "PLANT_MOBILE_LIVE_VERIFIED", "cards": 6, "width": 375,
                   "clicked_merchant_links": 0}
        self.assertEqual(self.evidence(PLANT_FIRST, receipt, browser)["counts"]["new"], 1)
        for bad in (dict(receipt, post_id=999), dict(receipt, new_posts=2),
                    dict(receipt, public_site_modified=False)):
            self.assertEqual(self.evidence(PLANT_FIRST, bad, browser)["counts"]["new"], 0)
        self.assertEqual(self.evidence(PLANT_FIRST, receipt, dict(browser, cards=1))["counts"]["new"], 0)
        self.assertEqual(self.evidence(PLANT_FIRST, receipt, browser,
                                       marker="##[group]Run unit tests")["counts"]["new"], 0)

    def test_daily_noop_and_update_are_distinct(self):
        receipt = {"state": "unchanged_public_verified", "post_id": 26152,
                   "slug": "xfit-os-rostlinne-proteiny-porovnani",
                   "url": "https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/",
                   "public_site_modified": False, "post_attempts": 0}
        browser = {"state": "PLANT_MOBILE_LIVE_VERIFIED", "cards": 6, "width": 375,
                   "clicked_merchant_links": 0}
        out = self.evidence(PLANT_DAILY, receipt, browser)
        self.assertEqual(out["counts"]["updated"], 0)
        self.assertEqual(out["verified_no_change_runs"], 1)
        receipt.update(state="live_verified", public_site_modified=True, post_attempts=1,
                       posts_changed=1, new_posts=0, deletes=0, redirects=0)
        self.assertEqual(self.evidence(PLANT_DAILY, receipt, browser)["counts"]["updated"], 1)
        self.assertEqual(self.evidence(PLANT_DAILY, dict(receipt, post_attempts=2),
                                       browser)["counts"]["updated"], 0)

    def test_beginner_inlink_is_an_existing_page_update(self):
        receipt = {"state": "PUBLIC_VERIFIED", "post_id": 25458,
                   "url": "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
                   "post_attempts": 1, "posts_changed": 1, "new_posts": 0,
                   "public_site_modified": True}
        browser = {"state": "PLANT_BEGINNER_MOBILE_VERIFIED", "width": 375,
                   "target": "https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/"}
        out = self.evidence(PLANT_HANDOFF, receipt, browser)
        self.assertEqual(out["counts"]["new"], 0)
        self.assertEqual(out["counts"]["updated"], 1)
        self.assertEqual(self.evidence(PLANT_HANDOFF, receipt, dict(browser, target="https://xfit.cz/"))["counts"]["updated"], 0)


class EquipmentProductionProofTests(unittest.TestCase):
    def evidence(self, name, receipt, browser, marker):
        log = "\n".join((json.dumps(receipt), marker, "##[endgroup]", json.dumps(receipt), json.dumps(browser)))
        return real_release_evidence([run(name=name)], "fake", fetch_jobs=jobs,
                                     fetch_log=lambda *_: log)

    def test_real_equipment_new_and_noop_proof(self):
        receipt = {"state": "PUBLIC_VERIFIED_NEW_POST", "post_id": 26154,
                   "slug": "xfit-os-vybaveni-na-domaci-cviceni-nabidky",
                   "url": "https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/",
                   "new_posts": 1, "public_site_modified": True}
        browser = {"state": "EQUIPMENT_MOBILE_LIVE_VERIFIED", "cards": 2, "width": 375,
                   "clicked_merchant_links": 0}
        marker = "##[group]Run python -m scripts.xfit_equipment_comparison apply"
        self.assertEqual(self.evidence(EQUIPMENT_FIRST, receipt, browser, marker)["counts"]["new"], 1)
        self.assertEqual(self.evidence(EQUIPMENT_FIRST, dict(receipt, post_id=26152), browser, marker)["counts"]["new"], 0)
        self.assertEqual(self.evidence(EQUIPMENT_FIRST, receipt, dict(browser, cards=1), marker)["counts"]["new"], 0)
        receipt.update(state="unchanged_public_verified", public_site_modified=False, post_attempts=0, new_posts=0)
        marker = "##[group]Run python -m scripts.xfit_equipment_refresh apply"
        out = self.evidence(EQUIPMENT_DAILY, receipt, browser, marker)
        self.assertEqual(out["verified_no_change_runs"], 1)
        self.assertEqual(out["counts"]["updated"], 0)

    def test_handoffs_require_exact_target_and_purpose(self):
        for name, (pid, slug, key, fragment) in EQUIPMENT_HANDOFFS.items():
            receipt = {"state": "PUBLIC_VERIFIED", "post_id": pid,
                       "url": "https://xfit.cz/" + slug + "/", "post_attempts": 1,
                       "posts_changed": 1, "new_posts": 0, "public_site_modified": True}
            browser = {"state": "EQUIPMENT_HANDOFF_MOBILE_VERIFIED", "width": 375,
                       "post_id": pid, "target": "https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/" + fragment}
            marker = "##[group]Run set -o pipefail\npython -m scripts.xfit_verified_inlink_release " + key + " apply"
            self.assertEqual(self.evidence(name, receipt, browser, marker)["counts"]["updated"], 1)
            self.assertEqual(self.evidence(name, receipt, dict(browser, target="https://xfit.cz/"), marker)["counts"]["updated"], 0)
            self.assertEqual(self.evidence(name, receipt, browser, "##[group]Run unit tests")["counts"]["updated"], 0)


class NavigationReleaseEvidenceTests(unittest.TestCase):
    def test_only_exact_actual_apply_and_later_mobile_proof(self):
        for name, (pid, slug, n, command, state, mobile, count_key) in ROUTE_RELEASES.items():
            receipt = {"state": state, "post_id": pid, "url": "https://xfit.cz/" + slug + "/",
                       count_key: n, "new_posts": 0, "posts_changed": 1, "post_attempts": 1,
                       "public_site_modified": True, "home_rank": 1, "category_rank": 1}
            browser = {"state": mobile, "post_id": pid, "width": 375, "choices": n, "merchant_clicks": 0}
            marker = "##[group]Run " + command
            def check(a,b,step=marker):
                log = "\n".join((json.dumps(a), step, "##[endgroup]", json.dumps(a), json.dumps(b)))
                return real_release_evidence([run(name=name)], "fake", fetch_jobs=jobs,
                                             fetch_log=lambda *_: log)
            self.assertEqual(check(receipt,browser)["counts"]["updated"], 1)
            self.assertEqual(check(receipt,dict(browser,choices=n+1))["counts"]["updated"], 0)
            self.assertEqual(check(dict(receipt,post_id=999),browser)["counts"]["updated"], 0)
            self.assertEqual(check(receipt,browser,"##[group]Run unit tests")["counts"]["updated"], 0)
            no_op=dict(receipt,public_site_modified=False,posts_changed=0,post_attempts=0)
            self.assertEqual(check(no_op,browser)["verified_no_change_runs"], 1)



class MatRecoveryEvidenceTests(unittest.TestCase):
    def test_exact_independent_historical_proof_is_not_a_new_write(self):
        from scripts.xfit_status_evidence import (MAT_RECOVERY_NAME, MAT_RECOVERY_RUN,
            MAT_ORIGINAL_RUN, MAT_RECOVERY_POSTS, MAT_RECOVERY_STEPS, MAT_TARGET)
        row = dict(name=MAT_RECOVERY_NAME,id=MAT_RECOVERY_RUN,status="completed",conclusion="success")
        source = []
        browser = []
        for pid, slug in MAT_RECOVERY_POSTS.items():
            source += [dict(state="LEGACY_MAT_STORED_METADATA_CHECK",post_id=pid,
                            changed_stored_fields=[],wordpress_writes=0),
                       dict(state="LEGACY_MAT_PRIOR_RELEASE_READONLY_VERIFIED",post_id=pid,
                            slug=slug,url="https://xfit.cz/"+slug+"/",original_run_id=MAT_ORIGINAL_RUN,
                            stored_metadata_preserved=True,public_site_modified=False,wordpress_writes=0,new_posts=0)]
            browser.append(dict(state="LEGACY_MAT_MOBILE_LIVE_VERIFIED",post_id=pid,width=375,
                                target=MAT_TARGET,merchant_clicks=0))
        job = dict(id=1,name="verify",status="completed",conclusion="success",
                   steps=[dict(name=n,status="completed",conclusion="success") for n in MAT_RECOVERY_STEPS])
        def check(src=source, mob=browser, run_row=row, job_row=job, marker=True):
            log = "\n".join([json.dumps(source[1]),
                "##[group]Run python - <<'PY'" if marker else "##[group]Run tests",
                "prove_prior_release(cfg, path)", "##[endgroup]",
                *map(json.dumps,src),
                "##[group]Run node tests/legacy_mat_mobile.cjs 3377 live",
                "node tests/legacy_mat_mobile.cjs 7487 live","##[endgroup]",
                *map(json.dumps,mob)])
            return real_release_evidence([run_row,run_row], "fake",
                fetch_jobs=lambda *_: {"jobs":[job_row]},fetch_log=lambda *_: log)
        out=check()
        self.assertEqual(out["mat_recovery"]["verified_post_ids"],[3377,7487])
        self.assertEqual(out["mat_recovery"]["new_writes"],0)
        self.assertEqual(out["counts"]["updated"],0)
        self.assertEqual(out["verified_events"],[])
        for bad in (check(src=source[:-1]),check(mob=browser[:-1]),check(marker=False),
                    check(src=[*source[:-1],dict(source[-1],wordpress_writes=1)]),
                    check(mob=[*browser[:-1],dict(browser[-1],width=390)]),
                    check(run_row=dict(row,id=123)),
                    check(job_row=dict(job,steps=job["steps"][1:]))):
            self.assertEqual(bad["mat_recovery"]["verified_post_ids"],[])
            self.assertTrue(bad["mat_recovery"]["unknown_run_ids"])
            self.assertEqual(bad["counts"]["updated"],0)


if __name__=="__main__":
    unittest.main()

class LegacyCreatineMatrixEvidenceTests(unittest.TestCase):
    def fixtures(self, failure=None, malformed=None):
        def fake_jobs(_rid,_token):
            return {"jobs":[{"id":pid,"name":"publish ("+str(pid)+")",
                "status":"completed","conclusion":"failure" if pid==failure else "success",
                "steps":[{"name":step,"status":"completed","conclusion":"success"}
                         for step in CREATINE_LEGACY_STEPS]}
                for pid in CREATINE_LEGACY_TARGETS]}
        def fake_log(pid,_token):
            slug=CREATINE_LEGACY_TARGETS[pid]
            common={"post_id":pid,"width":375,"target":"https://xfit.cz/xfit-os-kreatin-poradce/","merchant_clicks":0}
            steps=[
                ('python -m scripts.xfit_legacy_creatine_release "$POST_ID" snapshot',
                 {"state":"LEGACY_CREATINE_PREWRITE_BACKUP_READY","post_id":pid,"wordpress_writes":0,"change_required":True}),
                ('node tests/legacy_creatine_mobile.cjs "$POST_ID" preview',
                 {"state":"LEGACY_CREATINE_MOBILE_PREVIEW_VERIFIED",**common}),
                ('python -m scripts.xfit_legacy_creatine_release "$POST_ID" apply',
                 {"state":"PUBLIC_LEGACY_CREATINE_REVISION_VERIFIED","post_id":pid,"slug":slug,
                  "url":"https://xfit.cz/"+slug+"/","post_attempts":1,"posts_changed":1,
                  "new_posts":0,"deletes":0,"redirects":0,"public_site_modified":True}),
                ('node tests/legacy_creatine_mobile.cjs "$POST_ID" live',
                 {"state":"LEGACY_CREATINE_MOBILE_LIVE_VERIFIED",**common}),
            ]
            if pid==malformed:
                steps[-1][1]["post_id"]=999
            return "\n".join("##[group]Run "+cmd+"\n##[endgroup]\n"+json.dumps(value) for cmd,value in steps)
        return fake_jobs,fake_log

    def test_completed_matrix_counts_once_and_failed_sibling_does_not_erase_proof(self):
        for failure,malformed,n in [(None,None,3),(11882,None,2),(None,11863,2)]:
            j,l=self.fixtures(failure,malformed)
            r=run(name=CREATINE_LEGACY_NAME,conclusion="failure" if failure else "success")
            out=real_release_evidence([r,r],"fake",fetch_jobs=j,fetch_log=l)
            self.assertEqual(out["counts"]["updated"],n)
            self.assertEqual(out["counts"]["new"],0)
            self.assertEqual(len(out["unverified_runs"]),int(n!=3))
            if n!=3:
                self.assertEqual(out["unverified_runs"][0]["unverified_post_ids"],[failure or malformed])
