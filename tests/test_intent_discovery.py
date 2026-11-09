"""Two source-backed old posts are not rewritten until exact live link evidence."""
import unittest

from scripts import xfit_intent_discovery as discovery


def post(slug, body, post_id=1723, url_host="xfit.cz"):
    return {
        "id": post_id,
        "slug": slug,
        "status": "publish",
        "link": "https://" + url_host + "/" + slug + "/",
        "content": {"raw": body},
    }


class LegacyRoutingDiscoveryTests(unittest.TestCase):
    def test_exact_url_in_plain_text_is_not_real_internal_link(self):
        slug, target, _ = discovery.PRIORITY_LEGACY[0]
        body = "<p>Long useful public article on creatine and training.</p>" * 24
        body += "<p>Example printed address: " + target + "</p>"
        calls = []
        def fake(base, path, payload=None):
            self.assertIsNone(payload)
            calls.append(path)
            self.assertIn("context=edit", path)
            if "slug=" + slug in path:
                return [post(slug, body)]
            return []
        result = discovery.inspect_priority(request=fake,base="https://xfit.cz")
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]["state"], "SOURCE_VERIFIED")
        self.assertEqual(result[0]["target_already_linked"], False)
        self.assertEqual(result[0]["next_action"],
                         "EDITORIAL_REVIEW_BEFORE_ONE_POST")
        self.assertEqual(result[1]["state"], "UNKNOWN_NO_VERIFIED_SOURCE")
        self.assertEqual(result[1]["target_already_linked"], None)
        self.assertNotIn(body, str(result))
        self.assertTrue(all(not item.get("modified_wordpress", False) for item in result))

    def test_only_exact_anchor_counts_and_is_idempotent(self):
        slug,target,_ = discovery.PRIORITY_LEGACY[1]
        body = ("<p>Useful text.</p>" * 22 +
                '<a href="' + target + '">Podrobnosti o bezpečnosti</a>')
        def fake(base, path):
            if "slug=" + slug in path:
                return [post(slug, body, 2026)]
            return []
        result = discovery.inspect_priority(request=fake,base="https://xfit.cz")
        self.assertTrue(result[1]["target_already_linked"])
        self.assertEqual(result[1]["next_action"], "ALREADY_LINKED")
        self.assertEqual(result[1]["wp_post_id"], 2026)

    def test_invalid_identity_is_unknown_and_never_eligible(self):
        slug,target,_ = discovery.PRIORITY_LEGACY[0]
        body = "<p>Evidence.</p>" * 40
        for changed in (
            {"link": "https://evil.example/" + slug + "/"},
            {"link": "http://xfit.cz/" + slug + "/"},
            {"slug": "wrong-slug"},
            {"status": "draft"},
            {"content": {"raw": ""}},
        ):
            with self.subTest(changed=changed):
                doc = post(slug,body)
                doc.update(changed)
                def fake(base,path):
                    return [doc] if "slug=" + slug in path else []
                result = discovery.inspect_priority(request=fake,base="https://xfit.cz")
                self.assertEqual(result[0]["state"],
                                 "UNKNOWN_NO_VERIFIED_SOURCE")
                self.assertNotEqual(result[0]["next_action"],
                                    "EDITORIAL_REVIEW_BEFORE_ONE_POST")

    def test_api_failure_remains_unknown_without_echoing_exception(self):
        def broken(base,path):
            raise ValueError("SECRET or private content")
        result = discovery.inspect_priority(request=broken,base="https://xfit.cz")
        self.assertEqual(len(result), 2)
        self.assertNotIn("SECRET", str(result))
        self.assertTrue(all(x["next_action"]=="RECHECK_SOURCE" for x in result))


    def test_cross_topic_pages_get_both_relevant_ideas_without_fake_links(self):
        slug="kreatin-a-protein-pruvodce"
        body=("<p>Original useful explanation.</p>" * 75 +
              "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/" +
              '<a href="https://xfit.cz/xfit-os-kreatin-poradce/">Kreatin</a>')
        doc=post(slug,body)
        doc["title"]={"raw":"Kreatin a protein: co vybrat?"}
        ranked=discovery.rank_search_results({"kreatin":[doc],"protein":[doc]})
        self.assertEqual(len(ranked["candidates"]),2)
        by_topic={c["topic"]:c for c in ranked["candidates"]}
        self.assertTrue(by_topic["kreatin"]["already_has_target_link"])
        self.assertFalse(by_topic["protein"]["already_has_target_link"])
        self.assertEqual(by_topic["protein"]["next_action"],
                         "EDITORIAL_REVIEW_BEFORE_ONE_POST")
        self.assertEqual(ranked["search_coverage_complete"],True)
        self.assertNotIn(body, str(ranked))

    def test_protein_only_search_result_does_not_get_irrelevant_creatine_link(self):
        slug="protein-podle-etikety"
        doc=post(slug,"<p>Useful protein explanation.</p>" * 75)
        doc["title"]={"raw":"Protein podle etikety: co porovnat"}
        result=discovery.rank_search_results({"kreatin":[doc],"protein":[]})
        self.assertEqual(result["candidates"],[])

    def test_exact_page_cap_must_not_claim_complete_discovery(self):
        slug="kreatin-a-protein"
        doc=post(slug,"<p>Useful details.</p>" * 80)
        doc["title"]={"raw":"Kreatin a protein"}
        result=discovery.rank_search_results({
            "kreatin":[doc]*discovery.SEARCH_LIMIT,"protein":[]})
        self.assertEqual(result["search_results_saturated_topics"],["kreatin"])
        self.assertFalse(result["search_coverage_complete"])
        self.assertEqual(result["candidate_count_before_limit"],1)

    def test_unverified_canonical_never_becomes_edit_candidate(self):
        slug="kreatin-test"
        doc=post(slug,"<p>Useful details.</p>" * 75,url_host="elsewhere.cz")
        doc["title"]={"raw":"Jak vybrat kreatin"}
        result=discovery.rank_search_results({"kreatin":[doc],"protein":[]})
        self.assertEqual(result["candidates"],[])


    def test_pagination_gets_all_pages_then_proves_completion(self):
        calls=[]
        def fake(base,path):
            from urllib.parse import parse_qs
            qs=parse_qs(path.split("?",1)[1])
            self.assertEqual(qs["search"],["kreatin"])
            self.assertEqual(qs["status"],["publish"])
            self.assertEqual(qs["context"],["edit"])
            # Search only real article titles: avoid 11k archive content mentions.
            self.assertEqual(qs["search_columns[]"],["post_title"])
            self.assertEqual(qs["per_page"],["100"])
            calls.append(int(qs["page"][0]))
            page=int(qs["page"][0])
            return ([{"id":page*100+i,"slug":"kreatin-post-"+str(i),
                     "status":"publish"} for i in range(100)]
                    if page==1 else
                    [{"id":205,"slug":"kreatin-post-205","status":"publish"}])
        rows,report=discovery.fetch_topic_posts(
            "kreatin",request=fake,base="https://xfit.cz")
        self.assertEqual(calls,[1,2])
        self.assertEqual(len(rows),101)
        self.assertEqual(report,{"status":"COMPLETE","pages_fetched":2,
                                 "unique_rows":101})

    def test_maximum_page_requires_explicit_incomplete_status(self):
        def fake(base,path):
            return [{"id":x+1} for x in range(2)]
        rows,coverage=discovery.fetch_topic_posts(
            "protein",request=fake,base="https://xfit.cz",
            page_size=2,max_pages=2)
        self.assertEqual(len(rows),2)
        self.assertEqual(coverage["status"],"PAGE_CAP_REACHED")
        ranked=discovery.rank_search_results(
            {"kreatin":[],"protein":rows},
            coverage={"kreatin":{"status":"COMPLETE"},
                      "protein":coverage})
        self.assertEqual(ranked["search_topics_incomplete"],["protein"])
        self.assertFalse(ranked["search_coverage_complete"])
        self.assertEqual(ranked["search_results_saturated_topics"],["protein"])

    def test_partial_api_error_is_preserved_as_unknown_not_complete(self):
        calls=[]
        def fake(base,path):
            from urllib.parse import parse_qs
            page=int(parse_qs(path.split("?",1)[1])["page"][0])
            calls.append(page)
            if page==2:
                raise ValueError("private raw API error secret")
            return [{"id":i+1} for i in range(100)]
        rows,meta=discovery.fetch_topic_posts(
            "protein",request=fake,base="https://xfit.cz")
        self.assertEqual(calls,[1,2])
        self.assertEqual(meta,{"status":"READ_ERROR","pages_fetched":1,
                               "unique_rows":100})
        self.assertNotIn("private",str(meta))
        self.assertEqual(len(rows),100)

    def test_repeated_ids_dont_count_twice_or_create_more_review_targets(self):
        def fake(base,path):
            from urllib.parse import parse_qs
            page=int(parse_qs(path.split("?",1)[1])["page"][0])
            rows=[{"id":i+1} for i in range(100)]
            return rows if page==1 else rows[:8]+[{"id":401}]
        rows,meta=discovery.fetch_topic_posts(
            "kreatin",request=fake,base="https://xfit.cz")
        self.assertEqual(len(rows),101)
        self.assertEqual(meta["status"],"COMPLETE")
        self.assertEqual(meta["unique_rows"],101)

    def test_invalid_pagination_input_never_calls_wordpress(self):
        def never(*args):
            raise AssertionError("unexpected WP request")
        for topic,per_page,max_pages in [
            ("unknown",100,2),("kreatin",101,2),("protein",0,2),
            ("kreatin",100,discovery.MAX_SEARCH_PAGES+1),
            ("protein",True,2),("protein",100,False),
        ]:
            with self.subTest(topic=topic,per_page=per_page,max_pages=max_pages):
                with self.assertRaises(ValueError):
                    discovery.fetch_topic_posts(topic,request=never,
                                                page_size=per_page,
                                                max_pages=max_pages)

    def test_full_pagination_proves_completeness_even_over_first_page_limit(self):
        slug="kreatin-vyber"
        doc=post(slug,"<p>Useful creatine instructions.</p>"*100)
        doc["title"]={"raw":"Jak vybrat kreatin"}
        data=discovery.rank_search_results(
            {"kreatin":[doc],"protein":[]},
            coverage={"kreatin":{"status":"COMPLETE"},
                      "protein":{"status":"COMPLETE"}})
        self.assertTrue(data["search_coverage_complete"])
        self.assertEqual(data["search_topics_incomplete"],[])


if __name__=="__main__":
    unittest.main()
