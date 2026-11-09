const { chromium } = require("playwright");
const fs = require("fs");
const {navigatePublicGet} = require("../scripts/xfit_mobile_navigation.cjs");
const checks = [
  {name:"beginner",url:"https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",expected:"Doplňky stravy pro začátečníky",minH2:6,commercial:false},
  {name:"creatine",url:"https://xfit.cz/xfit-os-kreatin-poradce/",expected:"Jak vybrat kreatin",minH2:3,commercial:true},
  {name:"whey",url:"https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",expected:"Srovnání syrovátkových proteinů",minH2:3,commercial:true},
  {name:"protein-guide",url:"https://xfit.cz/xfit-os-protein-guide/",expected:"Jak vybrat protein",minH2:7,commercial:false},
  {name:"pilates-cardio",url:"https://xfit.cz/pilates-vs-kardio-co-je-lepsi-pro-hubnuti/",expected:"Pilates vs. kardio",minH2:6,commercial:false},
  {name:"creatine-kidney",url:"https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/",expected:"Kreatin, ledviny a játra",minH2:6,commercial:false},
  {name:"creatine-vs-protein",url:"https://xfit.cz/xfit-os-kreatin-nebo-protein/",expected:"Kreatin, nebo protein?",minH2:6,commercial:false},
  {name:"protein-intake",url:"https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",expected:"Kolik bílkovin denně",minH2:8,commercial:false},
  {name:"protein-meaning",url:"https://xfit.cz/jaky-je-vyznam-proteinu-pri-nabirani-svalove-hmoty/",expected:"Proč bílkoviny pomáhají růstu svalů?",minH2:8,commercial:false}
];
fs.mkdirSync("reports/browser-qa", {recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true});
let bad=false;
for(const spec of checks){
 const context=await browser.newContext({viewport:{width:375,height:812},deviceScaleFactor:1,hasTouch:true,isMobile:true,locale:"cs-CZ"});
 const page=await context.newPage();
 const failures=[];
 try{
  const {response,retries}=await navigatePublicGet(page,spec.url,{timeout:60000});
  if(!response || response.status()>=400)failures.push("http_"+(response?.status()||"none"));
  await page.waitForTimeout(1200);
  // A full-page screenshot does not automatically fetch off-screen lazy images.
  // Scroll to a real product as a visitor does, then assess loaded imagery.
  if(spec.commercial){
    const firstCard=page.locator(".xfit-product-card").first();
    if(await firstCard.count()){
      await firstCard.scrollIntoViewIfNeeded();
      await page.waitForTimeout(1600);
    }
  }
  const doc=await page.evaluate(()=>{
    const h1=[...document.querySelectorAll("h1")].map(n=>n.textContent.trim()).join(" | ");
    const h2=document.querySelectorAll("h2").length;
    const titles=[...document.querySelectorAll("h2")].map(n=>n.textContent.trim()).slice(0,15);
    const full=document.documentElement.scrollWidth;
    const inner=window.innerWidth;
    const details=document.querySelectorAll("details").length;
    const summaries=document.querySelectorAll("summary").length;
    const links=[...document.querySelectorAll('a[href*="namaximum.cz"]')];
    const missingSponsored=links.filter(n=>!n.relList.contains("sponsored")).length;
    const images=[...document.querySelectorAll("img")].filter(n=>n.getBoundingClientRect().width>30 && !n.alt);
    const productImages=[...document.querySelectorAll(".xfit-product-card img")];
    const brokenProductImages=productImages.filter(n=>n.complete && n.naturalWidth===0);
    const productImageStatus=productImages.slice(0,6).map(n=>({
      host:new URL(n.currentSrc||n.src).hostname,loaded:n.complete&&n.naturalWidth>0,
      renderedHeight:Math.round(n.getBoundingClientRect().height),
      naturalWidth:n.naturalWidth}));
    const firstCard=document.querySelector(".xfit-product-card");
    const firstCardImage=firstCard?.querySelector("img");
    const firstCardLink=firstCard?.querySelector('a[href*="namaximum.cz"]');
    const firstCTABox=firstCardLink?.getBoundingClientRect();
    const firstCTAStyle=firstCardLink?getComputedStyle(firstCardLink):null;
    const firstProductLoaded=!!(firstCardImage && firstCardImage.complete && firstCardImage.naturalWidth>0);
    const firstCTASize=firstCTABox?{
      height:Math.round(firstCTABox.height),width:Math.round(firstCTABox.width),
      background:firstCTAStyle.backgroundColor
    }:null;
    const themeImagesMissingAlt=images.slice(0,8).map(n=>({
      host:new URL(n.currentSrc||n.src).hostname,
      path:new URL(n.currentSrc||n.src).pathname.slice(0,120)}));
    const budgetHeading=document.querySelector('h2#xfit-vyber-podle-rozpoctu');
    const budgetDetails=[];
    if(budgetHeading){
      for(let node=budgetHeading.nextElementSibling;
          node && node.tagName.toLowerCase()!=="h2";
          node=node.nextElementSibling){
        if(node.tagName.toLowerCase()!=="details")continue;
        const summary=node.querySelector("summary");
        const anchors=[...node.querySelectorAll('a[href^="#xfit-offer-"]')];
        const cheapestPack=node.querySelectorAll('p[data-xfit-budget-choice="upfront"]');
        const cheapestUnit=node.querySelectorAll('p[data-xfit-budget-choice="unit"]');
        const sameWinner=node.querySelectorAll('p[data-xfit-budget-choice="same"]');
        const noOffers=summary?.textContent.includes("— 0 nabídek")||false;
        const packLink=cheapestPack[0]?.querySelector('a[href^="#xfit-offer-"]');
        const unitLink=cheapestUnit[0]?.querySelector('a[href^="#xfit-offer-"]');
        const goalsValid=noOffers ? (
          anchors.length===0 && cheapestPack.length===0 &&
          cheapestUnit.length===0 && sameWinner.length===0
        ) : (
          cheapestPack.length===1 && !!packLink &&
          ((cheapestUnit.length===1 && sameWinner.length===0 &&
            !!unitLink && unitLink.getAttribute("href")!==packLink.getAttribute("href") &&
            anchors.length===2) ||
           (sameWinner.length===1 && cheapestUnit.length===0 &&
            anchors.length===1))
        );
        budgetDetails.push({
          hasSummary:!!(summary&&summary.textContent.trim().startsWith("Do ")),
          badTarget:anchors.some(link=>{
            const id=(link.getAttribute("href")||"").slice(1);
            return !/^xfit-offer-[1-9][0-9]*$/.test(id) ||
                !document.getElementById(id);
          }),
          goalsValid,
          unexpectedOutbound:!!node.querySelector('a[href^="http"],a[onclick]'),
        });
      }
    }
    const budget={
      heading:!!budgetHeading,
      choices:budgetDetails.length,
      valid:budgetDetails.every(d=>d.hasSummary&&!d.badTarget&&d.goalsValid&&!d.unexpectedOutbound),
    };
    // Verify two useful buyer goals (or an explicitly shared winner) against
    // the *existing* source-verified product cards. No merchant click is made.
    const tradeoffHeading = document.querySelector("h2#xfit-price-tradeoff");
    const tradeoffRoot = tradeoffHeading?.parentElement;
    const tradeoffNodes = {
      upfront:[...document.querySelectorAll('p[data-xfit-tradeoff="upfront"]')],
      unit:[...document.querySelectorAll('p[data-xfit-tradeoff="unit"]')],
      same:[...document.querySelectorAll('p[data-xfit-tradeoff="same"]')],
      difference:[...document.querySelectorAll('p[data-xfit-tradeoff="difference"]')],
    };
    const tradeoffLinks=[...tradeoffNodes.upfront,...tradeoffNodes.unit]
      .flatMap(p=>[...p.querySelectorAll('a')]);
    const tradeoff={
      heading:!!tradeoffHeading,
      cards:document.querySelectorAll(".xfit-product-card").length,
      upfrontCount:tradeoffNodes.upfront.length,
      unitCount:tradeoffNodes.unit.length,
      sameCount:tradeoffNodes.same.length,
      diffCount:tradeoffNodes.difference.length,
      targetsValid:tradeoffLinks.every(a=>{
        const href=a.getAttribute("href")||"";
        return /^#xfit-offer-[1-9][0-9]*$/.test(href) &&
               !!document.getElementById(href.slice(1));
      }),
      goalsValid:tradeoffNodes.upfront.length===1 && (
        (tradeoffNodes.unit.length===1 &&
         tradeoffNodes.same.length===0 &&
         tradeoffNodes.difference.length===1 &&
         tradeoffLinks.length===2 &&
         tradeoffLinks[0].getAttribute("href")!==tradeoffLinks[1].getAttribute("href") &&
         /\d+[\s\u00a0]*,\d{2} Kč/.test(tradeoffNodes.difference[0].textContent)) ||
        (tradeoffNodes.unit.length===0 &&
         tradeoffNodes.same.length===1 &&
         tradeoffNodes.difference.length===0 && tradeoffLinks.length===1)
      ),
      noMerchantLinks:tradeoffLinks.every(a=>a.getAttribute("href")?.startsWith("#"))
    };
    const modelPortionRows=[
      ...document.querySelectorAll(".xfit-product-card .xfit-model-portion")
    ].map(n=>n.textContent.trim());
    const servingGrams=location.pathname.includes("kreatin-poradce")?3:30;
    const modelPortions={
      count:modelPortionRows.length,
      valid:modelPortionRows.every(t=>
        t.includes("Modelové porce po "+servingGrams+" g prášku") &&
        /[1-9][0-9]* celých porcí v balení/.test(t) &&
        t.includes("Kč za "+servingGrams+" g prášku")
      ),
      intro:document.body.textContent.includes("Co stojí modelová porce?"),
    };
    const feedNotices=[...document.querySelectorAll(".xfit-feed-retrieval")];
    const feedProvenance={
      noticeCount:feedNotices.length,
      explicitCatalogDate:feedNotices.every(el=>
        /\b[0-3]?[0-9]\. [01]?[0-9]\. 20[0-9]{2}\b/.test(el.textContent) &&
        el.textContent.includes("Datum označuje načtení katalogu") &&
        el.textContent.includes("Aktuální cenu, složení a dostupnost ověřte")
      ),
    };
    // A source-level nav tag isn't enough: prove the exact HTML anchors and
    // their intended targets survive real 375px WordPress/theme rendering.
    // Only inspect links; never trigger a merchant click or analytics event.
    const quickNavs=[...document.querySelectorAll('nav[aria-label="Rychlá navigace poradcem"]')];
    const quickLinks=quickNavs.length===1 ? [...quickNavs[0].querySelectorAll("a")] : [];
    const quickExpected=["#xfit-need","#xfit-offers"];
    const quickNav={
      count:quickNavs.length,
      countLinks:quickLinks.length,
      exactTargets:quickLinks.length===2 && quickLinks.every((a,i)=>
        a.getAttribute("href")===quickExpected[i] &&
        a.getAttribute("target")===null &&
        !a.hasAttribute("onclick")),
      noBuyOpen:document.querySelector("details#xfit-need")?.open===true,
      offerHeadingExists:!!document.querySelector("h2#xfit-offers"),
      resolvedOnce:quickExpected.every(href=>
        document.querySelectorAll('[id="'+href.slice(1)+'"]').length===1),
      noMerchantLinks:quickLinks.every(a=>
        (a.getAttribute("href")||"").startsWith("#")),
    };
    const checkoutParagraphs=[...document.querySelectorAll("p")].filter(p=>
      p.textContent.includes("Když objednáváte jen jedno balení"));
    const proteinCheckout={
      count:checkoutParagraphs.length,
      contentValid:checkoutParagraphs.length===1 && [
        "včetně dopravy a povinných poplatků",
        "nepřičítejte celou společnou dopravu každému balení",
        "Nepřidávejte nepotřebné doplňky",
        "nemusíte objednávat nic",
      ].every(term=>checkoutParagraphs[0].textContent.includes(term)),
      noNewCommercialLink:checkoutParagraphs.every(p=>!p.querySelector("a[href^='http']")),
    };
    const labelGuideLinks=[...document.querySelectorAll('a[href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/"]')];
    const firstDecisionHeading=document.querySelector("h2");
    const labelGuideBridge={
      count:labelGuideLinks.length,
      early:labelGuideLinks.length===1 && (!firstDecisionHeading ||
        !!(labelGuideLinks[0].compareDocumentPosition(firstDecisionHeading) & Node.DOCUMENT_POSITION_FOLLOWING)),
      clear:labelGuideLinks.length===1 &&
        labelGuideLinks[0].textContent.includes("nutriční etikety"),
    };
    // WordPress must preserve the native HTML5 "open" attribute after
    // publishing. A passing source unit test is NOT proof the mobile visitor
    // actually sees the no-purchase answer without interaction.
    const noPurchaseHeading=[...document.querySelectorAll("h2")]
      .find(h=>h.textContent.trim().startsWith("Než koupíte"));
    const noPurchaseQuestions=[];
    if(noPurchaseHeading){
      for(let el=noPurchaseHeading.nextElementSibling;
          el && el.tagName.toLowerCase()!=="h2";
          el=el.nextElementSibling){
        if(el.tagName.toLowerCase()==="details")
          noPurchaseQuestions.push(el);
      }
    }
    const firstNoPurchase=noPurchaseQuestions[0];
    const noPurchase={
      heading:!!noPurchaseHeading,
      questions:noPurchaseQuestions.length,
      firstOpen:!!firstNoPurchase?.open,
      firstSummary:!!firstNoPurchase?.querySelector("summary"),
      answerText:(firstNoPurchase?.textContent||"").trim(),
      remainingClosed:noPurchaseQuestions.slice(1,3)
        .every(el=>!el.open),
    };
    // Actual WordPress-rendered advice, not just the reviewed JSON or API.
    const proteinPackItems=[...document.querySelectorAll("li")].filter(
      li=>li.textContent.includes("Koupit velké balení jen kvůli nižší jednotkové ceně"));
    const proteinPackText=proteinPackItems[0]?.textContent||"";
    const proteinPackUse={
      count:proteinPackItems.length,
      hasArithmetic:proteinPackText.includes("1 000 g") &&
        proteinPackText.includes("40 porcí") &&
        proteinPackText.includes("20 týdnů"),
      hasRealLimits:proteinPackText.includes("Nejde o doporučenou dávku") &&
        proteinPackText.includes("po otevření") &&
        proteinPackText.includes("protein nemusíte kupovat"),
      oldAdviceAbsent:!document.body.textContent.includes(
        "Nakoupit obří balení neznámé příchutě"),
    };
    // Live WP must preserve the beginner's actual decision-to-next-step UX,
    // not only the source JSON checked in to the public repository.
    const beginnerHeading=document.querySelector("h2#zacatecnik-rozhodnuti");
    const beginnerDetails=[];
    if(beginnerHeading){
      for(let el=beginnerHeading.nextElementSibling;
          el && el.tagName.toLowerCase()!=="h2";
          el=el.nextElementSibling){
        if(el.tagName.toLowerCase()==="details")beginnerDetails.push(el);
      }
    }
    const beginnerExpected=[
      "#zacatecnik-rozpocet",
      "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
      "https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",
      "https://xfit.cz/xfit-os-protein-guide/",
    ];
    const beginnerLinks=beginnerDetails.map(d=>
      [...d.querySelectorAll("a")].map(a=>a.getAttribute("href")));
    // The live WP frontend inserts an unrelated "#" anchor in the fourth
    // detail. The source-bound goal links must each remain UNIQUE and exact;
    // audit the placeholder separately rather than misclassify it as a goal.
    const actualGoalLinks=beginnerLinks.map(urls=>urls.filter(url=>url!=="#"));
    const placeholderLinks=beginnerDetails.map(d=>
      [...d.querySelectorAll('a[href="#"]')].map(a=>({
        text:(a.textContent||"").trim().slice(0,90),
        className:String(a.className||"").slice(0,90),
      })));
    const beginnerGoals={
      heading:!!beginnerHeading,
      count:beginnerDetails.length,
      firstOpen:!!beginnerDetails[0]?.open,
      othersClosed:beginnerDetails.slice(1).every(d=>!d.open),
      firstAnswersNoBuy:(beginnerDetails[0]?.textContent||"").includes("Začněte bez suplementů"),
      firstBudgetReachable:!!document.querySelector("h2#zacatecnik-rozpocet"),
      linkTargetsValid:actualGoalLinks.length===4 &&
        actualGoalLinks.every((urls,i)=>urls.length===1 && urls[0]===beginnerExpected[i]),
      linkTargetsObserved:beginnerLinks.map(urls=>urls.map(url=>
        (url||"").slice(0,180))),
      linkTargetsExpected:beginnerExpected,
      placeholderLinksObserved:placeholderLinks,
      allNativeSummaries:beginnerDetails.every(d=>!!d.querySelector("summary")),
    };
    return {h1,h2,titles,viewport:inner,documentWidth:full,details,summaries,
        merchantLinks:links.length,missingSponsored,imagesMissingAlt:images.length,
        productImages:productImages.length,brokenProductImages:brokenProductImages.length,
        productImageStatus,themeImagesMissingAlt,firstProductLoaded,firstCTASize,
        hasViewportMeta:!!document.querySelector('meta[name="viewport"]'),budget,modelPortions,feedProvenance,labelGuideBridge,tradeoff,noPurchase,proteinPackUse,proteinCheckout,quickNav,beginnerGoals};
  });
  if(!doc.h1.includes(spec.expected))failures.push("h1_missing_expected");
  if(doc.h2<spec.minH2)failures.push("insufficient_h2");
  if(!doc.hasViewportMeta)failures.push("mobile_viewport_missing");
  if(spec.name==="beginner" && (!doc.beginnerGoals.heading ||
      doc.beginnerGoals.count!==4 || !doc.beginnerGoals.firstOpen ||
      !doc.beginnerGoals.othersClosed || !doc.beginnerGoals.firstAnswersNoBuy ||
      !doc.beginnerGoals.firstBudgetReachable ||
      !doc.beginnerGoals.linkTargetsValid ||
      !doc.beginnerGoals.allNativeSummaries))
    failures.push("beginner_goal_paths_not_visible_or_incomplete");
  if(spec.name==="beginner" && doc.beginnerGoals.count===4){
    const secondSummary=page.locator('h2#zacatecnik-rozhodnuti ~ details summary').nth(1);
    if(await secondSummary.count()){
      await secondSummary.focus();
      await page.keyboard.press("Enter");
      if(!await secondSummary.evaluate(el=>!!el.parentElement?.open))
        failures.push("beginner_goal_not_keyboard_accessible");
    }else failures.push("beginner_goal_not_keyboard_accessible");
  }
  if(spec.name==="protein-guide" &&
      (doc.proteinPackUse.count!==1 || !doc.proteinPackUse.hasArithmetic ||
       !doc.proteinPackUse.hasRealLimits || !doc.proteinPackUse.oldAdviceAbsent))
    failures.push("published_protein_pack_use_advice_not_visible_or_incomplete");
  if(spec.name==="protein-guide" && (!doc.proteinCheckout.contentValid ||
      doc.proteinCheckout.count!==1 || !doc.proteinCheckout.noNewCommercialLink))
    failures.push("published_protein_checkout_total_advice_missing_or_incomplete");
  if(spec.commercial && (doc.quickNav.count!==1 ||
      doc.quickNav.countLinks!==2 || !doc.quickNav.exactTargets ||
      !doc.quickNav.noBuyOpen || !doc.quickNav.offerHeadingExists ||
      !doc.quickNav.resolvedOnce || !doc.quickNav.noMerchantLinks))
    failures.push("live_mobile_adviser_shortcuts_missing_or_invalid");
  if(spec.commercial && (!doc.noPurchase.heading ||
      doc.noPurchase.questions!==3 || !doc.noPurchase.firstOpen ||
      !doc.noPurchase.firstSummary || !doc.noPurchase.remainingClosed ||
      !(spec.name==="creatine"
        ? doc.noPurchase.answerText.includes("nekoupit nic")
        : doc.noPurchase.answerText.includes("Proteinový prášek není") ||
          doc.noPurchase.answerText.includes("Proteinový prášek je praktický"))))
    failures.push("no_purchase_first_answer_not_visible_by_default");
  if(spec.commercial && (!doc.tradeoff.heading || !doc.tradeoff.goalsValid ||
       !doc.tradeoff.targetsValid || !doc.tradeoff.noMerchantLinks))
    failures.push("price_tradeoff_missing_or_invalid");
  if(spec.commercial && !doc.budget.heading)failures.push("budget_heading_missing");
  if(spec.commercial && doc.budget.choices!==3)failures.push("budget_choices_not_three");
  if(spec.commercial && !doc.budget.valid)failures.push("budget_choice_link_or_summary_invalid");
  if(spec.commercial && doc.budget.choices===3){
    const firstSummary=page.locator('h2#xfit-vyber-podle-rozpoctu ~ details summary').first();
    if(await firstSummary.count()){
      await firstSummary.focus();
      await page.keyboard.press("Enter");
      if(!await firstSummary.evaluate(el=>!!el.parentElement?.open)){
        failures.push("budget_first_choice_not_keyboard_accessible");
      }
    }else failures.push("budget_first_choice_not_keyboard_accessible");
  }
  if(spec.commercial && doc.modelPortions.count!==doc.merchantLinks)
    failures.push("model_portion_rows_not_matching_product_ctas");
  if(spec.commercial && (!doc.modelPortions.valid || !doc.modelPortions.intro))
    failures.push("model_portion_math_or_disclaimer_missing");
  if(spec.commercial && doc.feedProvenance.noticeCount!==1)
    failures.push("catalog_date_notice_missing_or_duplicate");
  if(spec.commercial && !doc.feedProvenance.explicitCatalogDate)
    failures.push("catalog_date_not_explained_as_retrieval");
  if(spec.name==="whey" && (doc.labelGuideBridge.count!==1 ||
      !doc.labelGuideBridge.early || !doc.labelGuideBridge.clear))
    failures.push("whey_label_price_education_link_missing_or_not_early");
  if(spec.commercial && !doc.merchantLinks)failures.push("merchant_links_missing");
  if(spec.commercial && doc.missingSponsored)failures.push("sponsored_rel_missing");
  if(spec.commercial && doc.brokenProductImages)failures.push("broken_product_images_"+doc.brokenProductImages);
  if(spec.commercial && !doc.firstProductLoaded)failures.push("first_product_photo_not_loaded_after_scroll");
  if(spec.commercial && (!doc.firstCTASize || doc.firstCTASize.height<44))failures.push("merchant_cta_tap_target_under_44px");
  if(["beginner","pilates-cardio","creatine-kidney","creatine-vs-protein","protein-intake","protein-meaning"].includes(spec.name) && doc.details<3)failures.push("interactive_details_missing");
  if(doc.documentWidth>doc.viewport+12)failures.push("horizontal_overflow_"+(doc.documentWidth-doc.viewport));
  await page.screenshot({path:"reports/browser-qa/"+spec.name+"-mobile.png",fullPage:true});
  console.log(JSON.stringify({page:spec.name,state:failures.length?"FAIL":"PASS",navigation_retries:retries,doc,failures}));
 }catch(e){failures.push("browser_fetch_error_"+e.name);console.log(JSON.stringify({page:spec.name,state:"ERROR",failures}));}
 await context.close();
 bad ||= failures.length>0;
}
await browser.close();
if(bad)process.exitCode=2;

})().catch(e=>{console.error(e);process.exitCode=2;});
