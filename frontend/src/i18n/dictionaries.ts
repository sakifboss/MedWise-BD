/**
 * All UI text in English and Bangla. `bn` must have exactly the shape of `en` (type-checked).
 * Medicine data from the database (names, strengths, medical text) is not translated here.
 */

export const LANGS = ["en", "bn"] as const;
export type Lang = (typeof LANGS)[number];
export const DEFAULT_LANG: Lang = "en";
export const LANG_COOKIE = "lang";

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as readonly string[]).includes(value);
}

function formatters(locale: string, currency: string, forms: Record<string, string>) {
  const number = (value: number, digits = 0) =>
    value.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return {
    /** Price per unit, two decimals: "Tk 1.20" / "৳১.২০". */
    price: (value: number) => `${currency}${number(value, 2)}`,
    priceRange(min: number, max: number) {
      return min === max ? this.price(min) : `${this.price(min)} – ${this.price(max)}`;
    },
    /** Whole taka for monthly totals: "Tk 360" / "৳৩৬০". */
    taka: (value: number) => `${currency}${number(Math.round(value))}`,
    int: (value: number) => number(value),
    date: (value: Date) =>
      value.toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Dhaka" }),
    score: (value: number) => number(value, 1),
    /** Dosage form as shown to the user; unknown forms are shown as stored. */
    form: (form: string) => forms[form] ?? form,
  };
}

const enPlural = (n: number, one: string, many: string) => (n === 1 ? one : many);

const en = {
  lang: "en" as Lang,
  meta: {
    title: "MedWise BD — quality-first medicine alternatives",
    description:
      "Find same-generic, same-strength medicine alternatives in Bangladesh, ranked by manufacturer quality and price.",
  },
  fmt: formatters("en-US", "Tk ", { tablet: "tablet", capsule: "capsule", suspension: "suspension" }),
  severity: { major: "Major", moderate: "Moderate", minor: "Minor" },
  nav: {
    main: "Main",
    scan: "Scan",
    interactions: "Interactions",
    /** Shown on the language button: the language you switch TO. */
    switchTo: "বাংলা",
    switchLabel: "বাংলায় দেখুন (View in Bangla)",
  },
  footer: {
    noAdvice: "MedWise BD compares medicines using its own database. It does not give medical advice.",
    sources:
      "Data: manufacturer quality from public regulator and company sources; prices are Arogga MRPs " +
      "(Nov 2026); medicine information from the NHS website and US FDA labels; interactions from " +
      "DDInter. Not official DGDA data.",
  },
  disclaimer: "Consult your doctor or pharmacist before changing any medicine.",
  back: { newSearch: "New search", byName: "Search by name instead", home: "Home" },
  notFound: {
    title: "Medicine not found",
    text: "We couldn’t find that medicine in our data. Try searching by brand or generic name.",
    action: "Search medicines",
  },
  errorPage: {
    title: "We couldn’t load this page",
    text: "The MedWise server may be starting up or temporarily unavailable. Please try again in a moment.",
    retry: "Try again",
  },
  home: {
    title: "Find a trusted alternative to your medicine",
    intro:
      "Search a brand or generic name to see every brand with the same medicine, strength and form, " +
      "ranked by manufacturer quality and price.",
    typeHint: "You can type in English or Bangla, e.g.",
    scanTitle: "Have a prescription?",
    scanText: "Take a photo and we’ll find alternatives for every medicine on it.",
    interactionsTitle: "Taking more than one medicine?",
    interactionsText: "Check them together for recorded interactions.",
    companiesTitle: "Who makes your medicine?",
    companiesText: "See each manufacturer's regulator approvals, score breakdown and sources.",
    howTitle: "How the ranking works",
  },
  how: {
    before: "Only brands with the ",
    same: "same generic, strength and form",
    middle: " are compared. Each gets a score out of 100: ",
    quality: "80% manufacturer quality",
    qualityDetail:
      " (plant approvals by US FDA, UK MHRA, EU GMP and TGA Australia, exports, compliance, recall " +
      "history, market trust) and ",
    price: "20% price",
    after: ".",
  },
  search: {
    label: "Search for a medicine",
    placeholder: "Brand or generic name, e.g. Napa",
    searching: "Searching",
    error: "Search is unavailable right now. Please try again.",
    noResults: (q: string) => `No medicines found for “${q}”. Check the spelling or try the generic name.`,
    showingBefore: "Showing results for “",
    showingAfter: "”",
    resultsLabel: "Search results",
    generic: "Generic",
    genericHint: "All brands, uses and interactions",
  },
  share: {
    heading: "Share with your pharmacist",
    share: "Share",
    copied: "Link copied",
    whatsapp: "WhatsApp",
    print: "Print / PDF",
    scanToOpen: "Scan to open this page",
    rankingIntro: (title: string) => `${title} on MedWise BD (same generic, strength and form):`,
    rankingLine: (rank: string, name: string, maker: string, price: string, score: string) =>
      `${rank}. ${name}, ${maker}, ${price}/unit, score ${score}`,
    yourMedicineLine: (name: string, rank: string) => `My medicine: ${name} (rank ${rank})`,
    prescriptionTitle: "My medicines on MedWise BD",
    prescriptionIntro: "My medicines and their top-ranked alternatives on MedWise BD:",
    prescriptionLine: (medicine: string, best: string, maker: string, price: string) =>
      `• ${medicine}: top-ranked ${best} (${maker}), ${price}/unit`,
    prescriptionCardText: "Send this list to your pharmacist or print it to take to the pharmacy.",
    pageTitle: "Medicines to discuss with your pharmacist",
    prepared: (date: string) => `Prepared with MedWise BD on ${date}. Prices are MRPs from Arogga.`,
    notFoundTitle: "This shared list is empty or out of date",
    notFoundText: "The link has no medicines we can find. Ask the sender to share it again.",
    topRanked: "Top-ranked",
    scoreLabel: (score: string) => `score ${score}`,
    perMonth: (cost: string) => `${cost}/month`,
    quantity: (amount: string, unit: string) => `Prescribed amount: ${amount} ${unit}`,
    totals: "Total per month",
  },
  manufacturer: {
    nav: "Companies",
    listTitle: "Manufacturers",
    listIntro:
      "Every manufacturer in our data, ranked by its quality score out of 100. This score is 80% of each " +
      "brand's ranking; price is the other 20%.",
    brandCount: (n: number) => `${n} ${enPlural(n, "brand", "brands")} in our data`,
    all: "All manufacturers",
    yearsActive: (years: string) => `${years} years in operation`,
    qualityScore: "Quality score",
    outOf100: "out of 100",
    rankOf: (rank: string, total: string) => `Rank ${rank} of ${total} manufacturers`,
    scoreNote: "This is the manufacturer part (80%) of every brand's score. Price makes up the other 20%.",
    approvalsTitle: "Plant approvals by strict regulators",
    approved: "Approved plant on record",
    notApproved: "No approved plant on record",
    approvalsNote:
      "Approvals are for factories (plants), not for each medicine: not every product of a company is made " +
      "in an approved plant.",
    breakdownTitle: "How the quality score is built",
    weight: (percent: string) => `${percent}% weight`,
    points: (points: string, max: string) => `${points} of ${max} points`,
    total: (score: string) => `Total: ${score} of 100`,
    factors: {
      certification: "Strict regulator approvals",
      export: "Export footprint",
      compliance: "Compliance",
      recall_history: "Recall history",
      market: "Market trust",
    },
    explain: {
      certification: (n: string) => `${n} of 4 strict regulators (US FDA, UK MHRA, EU GMP, TGA Australia)`,
      exportKnown: (countries: string, regulated: string) =>
        `Exports to ${countries} countries, including ${regulated} regulated markets`,
      exportUnknown: (regulated: string) =>
        `Exports to ${regulated} regulated markets; the number of countries is not known and counts as 0`,
      exportNone: "No export record in our data",
      compliance: (score: string) =>
        `Compliance score ${score}/100: 100 minus 15 for each documented adverse finding by a strict ` +
        "regulator in the last 5 years",
      recallUnavailable:
        "No structured recall data exists for Bangladesh, so every manufacturer gets the same score here. " +
        "It does not change any ranking.",
      recallNone: "No recall on record",
      recallCount: (n: string) => `${n} recalls on record`,
      marketKnown: (share: string, years: string) => `${share}% market share, ${years} years in operation`,
      marketUnknown: (years: string) =>
        `${years} years in operation; market share is not known and counts as 0`,
    },
    unknownTitle: "What we don’t know",
    unknown: {
      recall_history: "Recall history: no public, structured recall database exists for Bangladesh.",
      market_share: "Market share: no published figure was found for this company.",
      export_country_count: "Number of export countries: not published; only regulated markets are known.",
    },
    brandsTitle: "Brands in our data",
    noBrands: "None of this company’s brands are in our data yet.",
    sourcesTitle: "Sources",
    sourcesNote: "The approvals, exports, compliance and market figures on this page come from these public pages.",
    notFoundTitle: "Manufacturer not found",
    notFoundText: "We couldn’t find that manufacturer in our data.",
  },
  pwa: { install: "Install app" },
  voice: {
    start: "Search by voice",
    stop: "Stop listening",
    listening:
      "Listening… say a medicine name. Your browser turns speech into text; MedWise never receives the audio.",
    denied: "Microphone access is blocked. Allow it in your browser settings to search by voice.",
    noSpeech: "Didn’t hear anything. Tap the mic and say the medicine name.",
    failed: "Voice search isn’t working right now. Please type the name instead.",
  },
  alternatives: {
    title: (name: string) => `Alternatives to ${name}`,
  },
  ranking: {
    title: (generic: string, strength: string, form: string) => `${generic} ${strength} ${form} brands ranked`,
    subtitle: "All brands, ranked",
    listLabel: "Ranked brands",
    onlyOne: "No other brands with the same strength and form are in our data.",
    compared: (n: number) => `${n} brands compared.`,
    selectedTop: (name: string, total: number) => `${name} ranks highest of the ${total} brands compared.`,
    above: (above: number, name: string, total: number) =>
      `${above} ${enPlural(above, "brand ranks", "brands rank")} above ${name} (${total} compared).`,
    rank: (n: number) => `Rank ${n}`,
    yourMedicine: "Your medicine",
    approvals: "Plant approvals",
    perUnit: (price: string) => `${price} per unit`,
    priceSource: "price source",
    outOf100: "out of 100",
    howCalculated: "How this score was calculated",
    qualityWeight: "Quality (80% weight)",
    priceWeight: "Price (20% weight)",
    qualityFactors: "Quality factors",
    factors: {
      certification: "Stringent regulator approvals",
      export: "Export footprint",
      compliance: "Compliance",
      recall_history: "Recall history (lower is better)",
      market: "Market trust",
    },
    sources: (n: number) => `Sources for manufacturer data (${n})`,
  },
  savings: {
    title: "Monthly cost calculator",
    question: (form: string) =>
      form === "suspension"
        ? "How many bottles a month does your prescription say?"
        : `How many ${form}s a day does your prescription say?`,
    unit: (form: string) => (form === "suspension" ? "bottles a month" : `${form}s a day`),
    placeholder: "e.g. 2",
    noDoseNote: "Use the number on your prescription. MedWise BD does not suggest doses.",
    yourMedicine: "Your medicine:",
    perMonth: (cost: string) => `${cost} a month`,
    best: "Best ranked",
    cheapest: "Cheapest",
    rank: (n: string) => `(rank ${n})`,
    save: (month: string, year: string) => `save ${month} a month (${year} a year)`,
    more: (month: string) => `${month} more a month`,
    range: (min: string, max: string) => (min === max ? `Monthly cost: ${min}` : `Monthly cost: ${min} to ${max}`),
    current: "your current cost",
    same: "same cost",
    saveShort: (month: string) => `save ${month} a month`,
  },
  costSummary: {
    title: "Monthly cost of this prescription",
    note: "Enter the amounts written on your prescription. MedWise BD does not suggest doses.",
    yourBrand: "Your brand",
    best: "Best ranked",
    cheapest: "Cheapest",
    noBrands: "No brands in our data.",
    loading: "Loading prices…",
    total: "Total per month",
    counted: (counted: number, total: number) => `(${counted} of ${total} medicines)`,
    yourBrands: "Your brands",
    bestBrands: "Best-ranked brands",
    cheapestBrands: "Cheapest brands",
    pickAll: "Pick a brand for every medicine to see this.",
    sameAsNow: "same as now",
    save: (month: string, year: string) => `save ${month}/month · ${year}/year`,
    more: (month: string) => `${month}/month more`,
  },
  prescription: {
    metaDescription: "Read medicine names from a prescription photo and compare alternatives.",
    title: "Scan a prescription",
    intro:
      "We read the medicine names and strengths, you confirm them, then we show ranked alternatives for each.",
    reading: "Reading your prescription…",
    readingTime: "This usually takes 5–15 seconds.",
    errors: {
      unsupported_file: "That file isn’t a supported image. Please upload a JPEG, PNG, WebP or HEIC photo.",
      file_too_large: "That photo is too large. Please try a smaller photo.",
      ocr_busy: "Many prescriptions are being read right now. Please try again in a minute.",
      ocr_unavailable: "Prescription reading is unavailable right now. You can still search by name.",
      ocr_failed: "We couldn’t read that photo. Try a clearer, well-lit photo of the prescription.",
    } as Record<string, string>,
    unknownError: "Something went wrong. Please try again.",
    upload: {
      prompt: "Take or choose a photo of the prescription",
      formats: "JPEG, PNG, WebP or HEIC",
      choose: "Choose photo",
      readOnly: "Only medicine names and strengths are read.",
      readOnlyMore:
        "We never generate doses or medical advice, and you confirm every medicine before seeing results.",
      privacy:
        "Your photo is sent to Google Gemini to read the text and is not stored by MedWise. Google may use " +
        "images sent through its free API tier to improve its services, so avoid photos showing details " +
        "you don’t want shared.",
    },
    confirm: {
      heading: "Check the medicines we found",
      intro: "Handwriting can be misread. Confirm each medicine before we show results.",
      noneRead:
        "No medicines could be read from this photo. Try a clearer, well-lit photo, or add medicines by hand.",
      readAs: "Read as",
      remove: "Remove",
      removeLabel: (name: string) => `Remove ${name}`,
      which: "Which medicine is this?",
      matchLabel: (name: string) => `Match for ${name}`,
      genericOption: "Generic name: compare all brands",
      differentStrength: "Different strength from prescription",
      none: "None of these (skip this medicine)",
      notFound: "We couldn’t find this medicine in our data. Search for it below, or remove it.",
      searchFor: (name: string) => `Search for ${name}`,
      notListed: "Not listed? Search for it",
      add: "Add a medicine",
      skipped: (n: number) => `${n} ${enPlural(n, "medicine", "medicines")} without a match will be skipped.`,
      startOver: "Start over",
      show: (n: number) => (n > 0 ? `Show alternatives for ${n}` : "Show alternatives"),
    },
    medicineSearch: {
      placeholder: "Type a brand name",
      noBrands: "No brands found. Try another spelling.",
      unavailable: "Search is unavailable right now.",
    },
    results: {
      heading: "Your prescription",
      interactions: "Interactions between these medicines",
      alternatives: "Alternatives",
      loadError: "Couldn’t load alternatives for this medicine.",
      fullRanking: "See full ranking and reasons",
      edit: "Edit medicines",
      another: "Scan another prescription",
      alreadyTop: (name: string, total: number, score: string) =>
        `is already the top-ranked of ${total} ${enPlural(total, "brand", "brands")} (score ${score}).`,
      ranksOf: (name: string, rank: number, total: number, score: string) =>
        `${name} ranks #${rank} of ${total} (score ${score}).`,
      topRanked: "Top-ranked:",
      topDetail: (maker: string, score: string, price: string) => ` by ${maker} · score ${score} · ${price}/unit`,
    },
  },
  interactions: {
    metaDescription: "Check medicines together for interactions recorded in the MedWise database.",
    title: "Interaction checker",
    intro: "Add the medicines you take. We’ll show any interactions recorded between them in our data.",
    addLabel: "Add a medicine",
    placeholder: "Brand or generic name",
    full: (n: number) => `Up to ${n} medicines`,
    noResults: "No medicines found. Try another spelling.",
    unavailable: "Search is unavailable right now.",
    picked: "Medicines to check",
    remove: (label: string) => `Remove ${label}`,
    results: "Results",
    addTwoOrMore: "Add two or more medicines to check them together.",
    checking: "Checking interactions",
    error: "Couldn’t check interactions right now. Please try again.",
    noneRecorded: "No interactions recorded between these medicines",
    found: (n: number) => `${n} ${enPlural(n, "interaction", "interactions")} found`,
    duplicateTitle: "Same medicine more than once",
    duplicateText: (brands: string[], generic: string) => `${brands.join(" and ")} both contain ${generic}.`,
    addAtLeastTwo: "Add at least two different medicines to check interactions.",
    note: "Only interactions recorded in our data are shown. No result does not mean it is safe to combine medicines.",
    credit: "Interaction data:",
    generic: "Generic",
  },
  generic: {
    metaDescription: (name: string, drugClass: string) => `${name} (${drugClass}): brands, uses and interactions.`,
    compare: "Compare brands",
    usedFor: "Used for",
    sideEffects: "Possible side effects",
    precautions: "Precautions",
    interactions: "Interactions",
    notRecorded: "Not recorded.",
    noBrands: "No brands of this medicine are in our data yet.",
    brandCount: (n: number) => `${n} ${enPlural(n, "brand", "brands")}`,
    perUnit: (range: string) => `${range} per unit`,
    compareAction: "Compare",
    noInteractions: "No interactions are recorded in our data.",
    checkWith: (name: string) => `Check ${name} with your other medicines`,
    sourceBefore: "Medicine information from ",
    sourceAfter: ", condensed by MedWise BD.",
    sourceAfterTranslated: ", condensed by MedWise BD.",
    englishOnly: "",
  },
};

export type Dict = typeof en;

const bn: Dict = {
  lang: "bn",
  meta: {
    title: "MedWise BD — মান-প্রথম ওষুধের বিকল্প",
    description:
      "বাংলাদেশে একই জেনেরিক ও একই শক্তির ওষুধের বিকল্প খুঁজুন, প্রস্তুতকারকের মান ও দাম অনুযায়ী সাজানো।",
  },
  fmt: formatters("bn-BD", "৳", { tablet: "ট্যাবলেট", capsule: "ক্যাপসুল", suspension: "সাসপেনশন" }),
  severity: { major: "গুরুতর", moderate: "মাঝারি", minor: "সামান্য" },
  nav: {
    main: "প্রধান",
    scan: "স্ক্যান",
    interactions: "ইন্টারঅ্যাকশন",
    switchTo: "English",
    switchLabel: "View in English (ইংরেজিতে দেখুন)",
  },
  footer: {
    noAdvice: "MedWise BD নিজস্ব ডেটাবেস দিয়ে ওষুধের তুলনা করে। এটি কোনো চিকিৎসা পরামর্শ দেয় না।",
    sources:
      "ডেটা: প্রস্তুতকারকের মান নিয়ন্ত্রক সংস্থা ও কোম্পানির প্রকাশিত উৎস থেকে; দাম Arogga-র MRP " +
      "(নভেম্বর ২০২৬); ওষুধের তথ্য NHS ওয়েবসাইট ও US FDA লেবেল থেকে; ইন্টারঅ্যাকশন DDInter থেকে। " +
      "এটি DGDA-র সরকারি ডেটা নয়।",
  },
  disclaimer: "কোনো ওষুধ বদলানোর আগে আপনার ডাক্তার বা ফার্মাসিস্টের পরামর্শ নিন।",
  back: { newSearch: "নতুন খোঁজ", byName: "নাম দিয়ে খুঁজুন", home: "হোম" },
  notFound: {
    title: "ওষুধটি পাওয়া যায়নি",
    text: "আমাদের ডেটায় এই ওষুধটি পাওয়া যায়নি। ব্র্যান্ড বা জেনেরিক নাম দিয়ে খুঁজে দেখুন।",
    action: "ওষুধ খুঁজুন",
  },
  errorPage: {
    title: "পেজটি লোড করা যায়নি",
    text: "MedWise সার্ভার হয়তো চালু হচ্ছে বা সাময়িকভাবে বন্ধ আছে। কিছুক্ষণ পর আবার চেষ্টা করুন।",
    retry: "আবার চেষ্টা করুন",
  },
  home: {
    title: "আপনার ওষুধের একটি নির্ভরযোগ্য বিকল্প খুঁজুন",
    intro:
      "ব্র্যান্ড বা জেনেরিক নাম লিখে খুঁজুন। একই ওষুধ, একই শক্তি ও একই ধরনের সব ব্র্যান্ড দেখুন, " +
      "প্রস্তুতকারকের মান ও দাম অনুযায়ী সাজানো।",
    typeHint: "ইংরেজি বা বাংলায় লিখতে পারেন, যেমন",
    scanTitle: "প্রেসক্রিপশন আছে?",
    scanText: "ছবি তুলুন, এতে থাকা প্রতিটি ওষুধের বিকল্প আমরা খুঁজে দেব।",
    interactionsTitle: "একাধিক ওষুধ খাচ্ছেন?",
    interactionsText: "একসাথে খেলে কোনো ইন্টারঅ্যাকশন নথিভুক্ত আছে কি না দেখুন।",
    companiesTitle: "আপনার ওষুধ কারা তৈরি করে?",
    companiesText: "প্রতিটি প্রস্তুতকারকের নিয়ন্ত্রক অনুমোদন, নম্বরের হিসাব ও উৎস দেখুন।",
    howTitle: "র‍্যাঙ্কিং কীভাবে হয়",
  },
  how: {
    before: "শুধু ",
    same: "একই জেনেরিক, শক্তি ও ধরনের",
    middle: " ব্র্যান্ডগুলোর মধ্যে তুলনা করা হয়। প্রতিটি ব্র্যান্ড ১০০-র মধ্যে নম্বর পায়: ",
    quality: "৮০% প্রস্তুতকারকের মান",
    qualityDetail:
      " (US FDA, UK MHRA, EU GMP ও TGA Australia-র প্ল্যান্ট অনুমোদন, রপ্তানি, কমপ্লায়েন্স, রিকলের " +
      "ইতিহাস, বাজারে আস্থা) এবং ",
    price: "২০% দাম",
    after: "।",
  },
  search: {
    label: "ওষুধ খুঁজুন",
    placeholder: "ব্র্যান্ড বা জেনেরিক নাম, যেমন নাপা",
    searching: "খোঁজা হচ্ছে",
    error: "এই মুহূর্তে খোঁজা যাচ্ছে না। একটু পরে আবার চেষ্টা করুন।",
    noResults: (q: string) => `“${q}” নামে কোনো ওষুধ পাওয়া যায়নি। বানান দেখুন অথবা জেনেরিক নাম লিখে চেষ্টা করুন।`,
    showingBefore: "“",
    showingAfter: "”-এর ফলাফল দেখানো হচ্ছে",
    resultsLabel: "খোঁজার ফলাফল",
    generic: "জেনেরিক",
    genericHint: "সব ব্র্যান্ড, ব্যবহার ও ইন্টারঅ্যাকশন",
  },
  share: {
    heading: "ফার্মাসিস্টের সাথে শেয়ার করুন",
    share: "শেয়ার",
    copied: "লিংক কপি হয়েছে",
    whatsapp: "হোয়াটসঅ্যাপ",
    print: "প্রিন্ট / PDF",
    scanToOpen: "এই পেজটি খুলতে স্ক্যান করুন",
    rankingIntro: (title: string) => `MedWise BD-তে ${title} (একই জেনেরিক, শক্তি ও ধরন):`,
    rankingLine: (rank: string, name: string, maker: string, price: string, score: string) =>
      `${rank}. ${name}, ${maker}, প্রতি ইউনিট ${price}, নম্বর ${score}`,
    yourMedicineLine: (name: string, rank: string) => `আমার ওষুধ: ${name} (র‍্যাঙ্ক ${rank})`,
    prescriptionTitle: "MedWise BD-তে আমার ওষুধগুলো",
    prescriptionIntro: "MedWise BD-তে আমার ওষুধ ও সেগুলোর সেরা র‍্যাঙ্কের বিকল্প:",
    prescriptionLine: (medicine: string, best: string, maker: string, price: string) =>
      `• ${medicine}: সেরা র‍্যাঙ্ক ${best} (${maker}), প্রতি ইউনিট ${price}`,
    prescriptionCardText: "এই তালিকাটি ফার্মাসিস্টকে পাঠান, অথবা প্রিন্ট করে ফার্মেসিতে নিয়ে যান।",
    pageTitle: "ফার্মাসিস্টের সাথে আলোচনার জন্য ওষুধের তালিকা",
    prepared: (date: string) => `MedWise BD দিয়ে তৈরি, ${date}। দাম Arogga-র MRP।`,
    notFoundTitle: "শেয়ার করা তালিকাটি খালি বা পুরোনো",
    notFoundText: "এই লিংকে আমাদের ডেটার কোনো ওষুধ নেই। যিনি পাঠিয়েছেন তাঁকে আবার শেয়ার করতে বলুন।",
    topRanked: "সেরা র‍্যাঙ্ক",
    scoreLabel: (score: string) => `নম্বর ${score}`,
    perMonth: (cost: string) => `মাসে ${cost}`,
    quantity: (amount: string, unit: string) => `প্রেসক্রিপশনের পরিমাণ: ${amount} ${unit}`,
    totals: "মাসে মোট",
  },
  manufacturer: {
    nav: "কোম্পানি",
    listTitle: "প্রস্তুতকারক কোম্পানি",
    listIntro:
      "আমাদের ডেটার সব প্রস্তুতকারক, ১০০-র মধ্যে মানের নম্বর অনুযায়ী সাজানো। প্রতিটি ব্র্যান্ডের র‍্যাঙ্কিংয়ে " +
      "এই নম্বরের গুরুত্ব ৮০%; বাকি ২০% দাম।",
    brandCount: (n: number) => `আমাদের ডেটায় ${n.toLocaleString("bn-BD")}টি ব্র্যান্ড`,
    all: "সব প্রস্তুতকারক",
    yearsActive: (years: string) => `${years} বছর ধরে চালু`,
    qualityScore: "মানের নম্বর",
    outOf100: "১০০-র মধ্যে",
    rankOf: (rank: string, total: string) => `${total}টি প্রস্তুতকারকের মধ্যে র‍্যাঙ্ক ${rank}`,
    scoreNote: "এটি প্রতিটি ব্র্যান্ডের নম্বরের প্রস্তুতকারক অংশ (৮০%)। বাকি ২০% আসে দাম থেকে।",
    approvalsTitle: "কঠোর নিয়ন্ত্রক সংস্থার প্ল্যান্ট অনুমোদন",
    approved: "অনুমোদিত প্ল্যান্টের রেকর্ড আছে",
    notApproved: "অনুমোদিত প্ল্যান্টের রেকর্ড নেই",
    approvalsNote:
      "অনুমোদন কারখানার (প্ল্যান্টের) জন্য, প্রতিটি ওষুধের জন্য নয়: কোম্পানির সব ওষুধ অনুমোদিত প্ল্যান্টে " +
      "তৈরি হয় না।",
    breakdownTitle: "মানের নম্বর কীভাবে তৈরি হয়",
    weight: (percent: string) => `${percent}% গুরুত্ব`,
    points: (points: string, max: string) => `${max}-এর মধ্যে ${points}`,
    total: (score: string) => `মোট: ১০০-র মধ্যে ${score}`,
    factors: {
      certification: "কঠোর নিয়ন্ত্রক সংস্থার অনুমোদন",
      export: "রপ্তানির পরিধি",
      compliance: "কমপ্লায়েন্স (নিয়ম মানা)",
      recall_history: "রিকলের ইতিহাস",
      market: "বাজারে আস্থা",
    },
    explain: {
      certification: (n: string) => `৪টির মধ্যে ${n}টি কঠোর নিয়ন্ত্রক সংস্থা (US FDA, UK MHRA, EU GMP, TGA Australia)`,
      exportKnown: (countries: string, regulated: string) =>
        `${countries}টি দেশে রপ্তানি করে, এর মধ্যে ${regulated}টি নিয়ন্ত্রিত বাজার`,
      exportUnknown: (regulated: string) =>
        `${regulated}টি নিয়ন্ত্রিত বাজারে রপ্তানি করে; মোট দেশের সংখ্যা জানা নেই, তাই ০ ধরা হয়েছে`,
      exportNone: "আমাদের ডেটায় রপ্তানির কোনো তথ্য নেই",
      compliance: (score: string) =>
        `কমপ্লায়েন্স স্কোর ${score}/১০০: গত ৫ বছরে কঠোর নিয়ন্ত্রক সংস্থার প্রতিটি নথিভুক্ত বিরূপ পর্যবেক্ষণের ` +
        "জন্য ১০০ থেকে ১৫ কমে",
      recallUnavailable:
        "বাংলাদেশে রিকলের কোনো সুবিন্যস্ত ডেটা নেই, তাই এখানে সব প্রস্তুতকারক একই নম্বর পায়। " +
        "এতে কোনো র‍্যাঙ্কিং বদলায় না।",
      recallNone: "কোনো রিকলের রেকর্ড নেই",
      recallCount: (n: string) => `${n}টি রিকলের রেকর্ড আছে`,
      marketKnown: (share: string, years: string) => `বাজারের ${share}% অংশ, ${years} বছর ধরে চালু`,
      marketUnknown: (years: string) => `${years} বছর ধরে চালু; বাজারের অংশ জানা নেই, তাই ০ ধরা হয়েছে`,
    },
    unknownTitle: "যা আমরা জানি না",
    unknown: {
      recall_history: "রিকলের ইতিহাস: বাংলাদেশে রিকলের কোনো প্রকাশ্য, সুবিন্যস্ত ডেটাবেস নেই।",
      market_share: "বাজারের অংশ: এই কোম্পানির কোনো প্রকাশিত সংখ্যা পাওয়া যায়নি।",
      export_country_count: "রপ্তানির দেশের সংখ্যা: প্রকাশিত নয়; শুধু নিয়ন্ত্রিত বাজারগুলো জানা আছে।",
    },
    brandsTitle: "আমাদের ডেটায় থাকা ব্র্যান্ড",
    noBrands: "এই কোম্পানির কোনো ব্র্যান্ড এখনো আমাদের ডেটায় নেই।",
    sourcesTitle: "উৎস",
    sourcesNote: "এই পেজের অনুমোদন, রপ্তানি, কমপ্লায়েন্স ও বাজারের তথ্য এই প্রকাশ্য পেজগুলো থেকে নেওয়া।",
    notFoundTitle: "প্রস্তুতকারক পাওয়া যায়নি",
    notFoundText: "আমাদের ডেটায় এই প্রস্তুতকারক পাওয়া যায়নি।",
  },
  pwa: { install: "অ্যাপ ইনস্টল করুন" },
  voice: {
    start: "কথা বলে খুঁজুন",
    stop: "শোনা বন্ধ করুন",
    listening:
      "শুনছি… ওষুধের নাম বলুন। আপনার ব্রাউজার কথাকে লেখায় রূপান্তর করে; MedWise কোনো অডিও পায় না।",
    denied: "মাইক্রোফোন ব্যবহারের অনুমতি বন্ধ আছে। কথা বলে খুঁজতে ব্রাউজারের সেটিংসে অনুমতি দিন।",
    noSpeech: "কিছু শোনা যায়নি। মাইকে চাপ দিয়ে ওষুধের নাম বলুন।",
    failed: "এই মুহূর্তে কথা বলে খোঁজা যাচ্ছে না। নামটি লিখে খুঁজুন।",
  },
  alternatives: {
    title: (name: string) => `${name}-এর বিকল্প`,
  },
  ranking: {
    title: (generic: string, strength: string, form: string) => `${generic} ${strength} ${form}: ব্র্যান্ডের র‍্যাঙ্কিং`,
    subtitle: "সব ব্র্যান্ড, র‍্যাঙ্ক অনুযায়ী",
    listLabel: "র‍্যাঙ্ক করা ব্র্যান্ড",
    onlyOne: "একই শক্তি ও ধরনের অন্য কোনো ব্র্যান্ড আমাদের ডেটায় নেই।",
    compared: (n: number) => `${n.toLocaleString("bn-BD")}টি ব্র্যান্ডের তুলনা করা হয়েছে।`,
    selectedTop: (name: string, total: number) =>
      `তুলনা করা ${total.toLocaleString("bn-BD")}টি ব্র্যান্ডের মধ্যে ${name} সবার উপরে।`,
    above: (above: number, name: string, total: number) =>
      `${name}-এর উপরে আছে ${above.toLocaleString("bn-BD")}টি ব্র্যান্ড (মোট ${total.toLocaleString("bn-BD")}টির তুলনা)।`,
    rank: (n: number) => `র‍্যাঙ্ক ${n.toLocaleString("bn-BD")}`,
    yourMedicine: "আপনার ওষুধ",
    approvals: "প্ল্যান্ট অনুমোদন",
    perUnit: (price: string) => `প্রতি ইউনিট ${price}`,
    priceSource: "দামের উৎস",
    outOf100: "১০০-র মধ্যে",
    howCalculated: "এই নম্বর কীভাবে হিসাব করা হলো",
    qualityWeight: "মান (৮০% গুরুত্ব)",
    priceWeight: "দাম (২০% গুরুত্ব)",
    qualityFactors: "মানের উপাদানগুলো",
    factors: {
      certification: "কঠোর নিয়ন্ত্রক সংস্থার অনুমোদন",
      export: "রপ্তানির পরিধি",
      compliance: "কমপ্লায়েন্স (নিয়ম মানা)",
      recall_history: "রিকলের ইতিহাস (কম হলে ভালো)",
      market: "বাজারে আস্থা",
    },
    sources: (n: number) => `প্রস্তুতকারকের তথ্যের উৎস (${n.toLocaleString("bn-BD")})`,
  },
  savings: {
    title: "মাসিক খরচের হিসাব",
    question: (form: string) =>
      form === "suspension"
        ? "প্রেসক্রিপশন অনুযায়ী মাসে কয় বোতল লাগে?"
        : `প্রেসক্রিপশনে দিনে কয়টি ${form === "capsule" ? "ক্যাপসুল" : "ট্যাবলেট"} লেখা আছে?`,
    unit: (form: string) =>
      form === "suspension" ? "বোতল, মাসে" : `${form === "capsule" ? "ক্যাপসুল" : "ট্যাবলেট"}, দিনে`,
    placeholder: "যেমন ২",
    noDoseNote: "প্রেসক্রিপশনে যা লেখা আছে সেই সংখ্যা দিন। MedWise BD কোনো ডোজ বলে দেয় না।",
    yourMedicine: "আপনার ওষুধ:",
    perMonth: (cost: string) => `মাসে ${cost}`,
    best: "সেরা র‍্যাঙ্কের",
    cheapest: "সবচেয়ে সস্তা",
    rank: (n: string) => `(র‍্যাঙ্ক ${n})`,
    save: (month: string, year: string) => `মাসে ${month} বাঁচবে (বছরে ${year})`,
    more: (month: string) => `মাসে ${month} বেশি`,
    range: (min: string, max: string) => (min === max ? `মাসিক খরচ: ${min}` : `মাসিক খরচ: ${min} থেকে ${max}`),
    current: "আপনার বর্তমান খরচ",
    same: "একই খরচ",
    saveShort: (month: string) => `মাসে ${month} বাঁচবে`,
  },
  costSummary: {
    title: "এই প্রেসক্রিপশনের মাসিক খরচ",
    note: "প্রেসক্রিপশনে লেখা পরিমাণ দিন। MedWise BD কোনো ডোজ বলে দেয় না।",
    yourBrand: "আপনার ব্র্যান্ড",
    best: "সেরা র‍্যাঙ্কের",
    cheapest: "সবচেয়ে সস্তা",
    noBrands: "আমাদের ডেটায় কোনো ব্র্যান্ড নেই।",
    loading: "দাম লোড হচ্ছে…",
    total: "মাসে মোট",
    counted: (counted: number, total: number) =>
      `(${total.toLocaleString("bn-BD")}টির মধ্যে ${counted.toLocaleString("bn-BD")}টি ওষুধ)`,
    yourBrands: "আপনার ব্র্যান্ডগুলো",
    bestBrands: "সেরা র‍্যাঙ্কের ব্র্যান্ড",
    cheapestBrands: "সবচেয়ে সস্তা ব্র্যান্ড",
    pickAll: "এটি দেখতে প্রতিটি ওষুধের ব্র্যান্ড বেছে নিন।",
    sameAsNow: "এখনকার মতোই",
    save: (month: string, year: string) => `মাসে ${month} · বছরে ${year} বাঁচবে`,
    more: (month: string) => `মাসে ${month} বেশি`,
  },
  prescription: {
    metaDescription: "প্রেসক্রিপশনের ছবি থেকে ওষুধের নাম পড়ে বিকল্পের তুলনা করুন।",
    title: "প্রেসক্রিপশন স্ক্যান করুন",
    intro: "আমরা ওষুধের নাম ও শক্তি পড়ি, আপনি সেগুলো নিশ্চিত করেন, তারপর প্রতিটির র‍্যাঙ্ক করা বিকল্প দেখাই।",
    reading: "আপনার প্রেসক্রিপশন পড়া হচ্ছে…",
    readingTime: "সাধারণত ৫–১৫ সেকেন্ড লাগে।",
    errors: {
      unsupported_file: "এই ফাইলটি সমর্থিত ছবি নয়। JPEG, PNG, WebP বা HEIC ছবি দিন।",
      file_too_large: "ছবিটি অনেক বড়। একটু ছোট ছবি দিন।",
      ocr_busy: "এখন অনেক প্রেসক্রিপশন পড়া হচ্ছে। এক মিনিট পর আবার চেষ্টা করুন।",
      ocr_unavailable: "এই মুহূর্তে প্রেসক্রিপশন পড়া যাচ্ছে না। আপনি নাম দিয়ে খুঁজতে পারেন।",
      ocr_failed: "ছবিটি পড়া যায়নি। আরও পরিষ্কার, ভালো আলোতে তোলা ছবি দিন।",
    },
    unknownError: "কিছু একটা সমস্যা হয়েছে। আবার চেষ্টা করুন।",
    upload: {
      prompt: "প্রেসক্রিপশনের ছবি তুলুন বা বেছে নিন",
      formats: "JPEG, PNG, WebP বা HEIC",
      choose: "ছবি বেছে নিন",
      readOnly: "শুধু ওষুধের নাম ও শক্তি পড়া হয়।",
      readOnlyMore: "আমরা কখনো ডোজ বা চিকিৎসা পরামর্শ তৈরি করি না, আর ফলাফল দেখার আগে আপনি প্রতিটি ওষুধ নিশ্চিত করবেন।",
      privacy:
        "লেখা পড়ার জন্য আপনার ছবি Google Gemini-তে পাঠানো হয়, MedWise ছবিটি সংরক্ষণ করে না। Google তাদের ফ্রি " +
        "API-তে পাঠানো ছবি নিজেদের সেবা উন্নত করতে ব্যবহার করতে পারে, তাই যে তথ্য শেয়ার করতে চান না তা " +
        "ছবিতে না রাখাই ভালো।",
    },
    confirm: {
      heading: "আমরা যে ওষুধগুলো পেয়েছি তা যাচাই করুন",
      intro: "হাতের লেখা ভুল পড়া হতে পারে। ফলাফল দেখানোর আগে প্রতিটি ওষুধ নিশ্চিত করুন।",
      noneRead: "এই ছবি থেকে কোনো ওষুধ পড়া যায়নি। আরও পরিষ্কার, ভালো আলোতে তোলা ছবি দিন, অথবা নিজে ওষুধ যোগ করুন।",
      readAs: "যা পড়া হয়েছে",
      remove: "বাদ দিন",
      removeLabel: (name: string) => `${name} বাদ দিন`,
      which: "এটি কোন ওষুধ?",
      matchLabel: (name: string) => `${name}-এর মিল`,
      genericOption: "জেনেরিক নাম: সব ব্র্যান্ডের তুলনা",
      differentStrength: "প্রেসক্রিপশনের চেয়ে ভিন্ন শক্তি",
      none: "এগুলোর কোনোটিই নয় (এই ওষুধটি বাদ যাবে)",
      notFound: "আমাদের ডেটায় এই ওষুধটি পাওয়া যায়নি। নিচে খুঁজুন, অথবা বাদ দিন।",
      searchFor: (name: string) => `${name} খুঁজুন`,
      notListed: "তালিকায় নেই? খুঁজে দেখুন",
      add: "ওষুধ যোগ করুন",
      skipped: (n: number) => `মিল না পাওয়া ${n.toLocaleString("bn-BD")}টি ওষুধ বাদ যাবে।`,
      startOver: "নতুন করে শুরু",
      show: (n: number) => (n > 0 ? `${n.toLocaleString("bn-BD")}টির বিকল্প দেখুন` : "বিকল্প দেখুন"),
    },
    medicineSearch: {
      placeholder: "ব্র্যান্ডের নাম লিখুন",
      noBrands: "কোনো ব্র্যান্ড পাওয়া যায়নি। অন্য বানানে চেষ্টা করুন।",
      unavailable: "এই মুহূর্তে খোঁজা যাচ্ছে না।",
    },
    results: {
      heading: "আপনার প্রেসক্রিপশন",
      interactions: "এই ওষুধগুলোর মধ্যে ইন্টারঅ্যাকশন",
      alternatives: "বিকল্প",
      loadError: "এই ওষুধের বিকল্প লোড করা যায়নি।",
      fullRanking: "পুরো র‍্যাঙ্কিং ও কারণ দেখুন",
      edit: "ওষুধ সম্পাদনা করুন",
      another: "আরেকটি প্রেসক্রিপশন স্ক্যান করুন",
      alreadyTop: (name: string, total: number, score: string) =>
        `আগে থেকেই ${total.toLocaleString("bn-BD")}টি ব্র্যান্ডের মধ্যে সবার উপরে (নম্বর ${score})।`,
      ranksOf: (name: string, rank: number, total: number, score: string) =>
        `${total.toLocaleString("bn-BD")}টির মধ্যে ${name}-এর র‍্যাঙ্ক ${rank.toLocaleString("bn-BD")} (নম্বর ${score})।`,
      topRanked: "সেরা র‍্যাঙ্ক:",
      topDetail: (maker: string, score: string, price: string) => ` (${maker}) · নম্বর ${score} · প্রতি ইউনিট ${price}`,
    },
  },
  interactions: {
    metaDescription: "MedWise ডেটাবেসে নথিভুক্ত ইন্টারঅ্যাকশন আছে কি না, একাধিক ওষুধ একসাথে যাচাই করুন।",
    title: "ইন্টারঅ্যাকশন যাচাই",
    intro: "আপনি যে ওষুধগুলো খান সেগুলো যোগ করুন। আমাদের ডেটায় এদের মধ্যে নথিভুক্ত কোনো ইন্টারঅ্যাকশন থাকলে দেখাব।",
    addLabel: "ওষুধ যোগ করুন",
    placeholder: "ব্র্যান্ড বা জেনেরিক নাম",
    full: (n: number) => `সর্বোচ্চ ${n.toLocaleString("bn-BD")}টি ওষুধ`,
    noResults: "কোনো ওষুধ পাওয়া যায়নি। অন্য বানানে চেষ্টা করুন।",
    unavailable: "এই মুহূর্তে খোঁজা যাচ্ছে না।",
    picked: "যে ওষুধগুলো যাচাই হবে",
    remove: (label: string) => `${label} বাদ দিন`,
    results: "ফলাফল",
    addTwoOrMore: "একসাথে যাচাই করতে দুই বা তার বেশি ওষুধ যোগ করুন।",
    checking: "ইন্টারঅ্যাকশন যাচাই হচ্ছে",
    error: "এই মুহূর্তে ইন্টারঅ্যাকশন যাচাই করা যাচ্ছে না। আবার চেষ্টা করুন।",
    noneRecorded: "এই ওষুধগুলোর মধ্যে কোনো ইন্টারঅ্যাকশন নথিভুক্ত নেই",
    found: (n: number) => `${n.toLocaleString("bn-BD")}টি ইন্টারঅ্যাকশন পাওয়া গেছে`,
    duplicateTitle: "একই ওষুধ একাধিকবার",
    duplicateText: (brands: string[], generic: string) => `${brands.join(" ও ")}, দুটিতেই ${generic} আছে।`,
    addAtLeastTwo: "ইন্টারঅ্যাকশন যাচাই করতে অন্তত দুটি ভিন্ন ওষুধ যোগ করুন।",
    note: "শুধু আমাদের ডেটায় নথিভুক্ত ইন্টারঅ্যাকশন দেখানো হয়। কোনো ফল না আসা মানে এই নয় যে ওষুধগুলো একসাথে খাওয়া নিরাপদ।",
    credit: "ইন্টারঅ্যাকশনের ডেটা:",
    generic: "জেনেরিক",
  },
  generic: {
    metaDescription: (name: string, drugClass: string) => `${name} (${drugClass}): ব্র্যান্ড, ব্যবহার ও ইন্টারঅ্যাকশন।`,
    compare: "ব্র্যান্ডের তুলনা",
    usedFor: "যে কাজে ব্যবহৃত হয়",
    sideEffects: "সম্ভাব্য পার্শ্বপ্রতিক্রিয়া",
    precautions: "সতর্কতা",
    interactions: "ইন্টারঅ্যাকশন",
    notRecorded: "নথিভুক্ত নেই।",
    noBrands: "এই ওষুধের কোনো ব্র্যান্ড এখনো আমাদের ডেটায় নেই।",
    brandCount: (n: number) => `${n.toLocaleString("bn-BD")}টি ব্র্যান্ড`,
    perUnit: (range: string) => `প্রতি ইউনিট ${range}`,
    compareAction: "তুলনা করুন",
    noInteractions: "আমাদের ডেটায় কোনো ইন্টারঅ্যাকশন নথিভুক্ত নেই।",
    checkWith: (name: string) => `আপনার অন্য ওষুধের সাথে ${name} যাচাই করুন`,
    sourceBefore: "ওষুধের তথ্যের উৎস: ",
    sourceAfter: " (MedWise BD সংক্ষেপ করেছে)।",
    sourceAfterTranslated: " (MedWise BD সংক্ষেপ করেছে; বাংলা অনুবাদ টিম পর্যালোচনা করেছে)।",
    englishOnly: "কিছু অংশের বাংলা অনুবাদ এখনো পর্যালোচনাধীন, তাই সেগুলো ইংরেজিতে দেখানো হচ্ছে।",
  },
};

export const DICTIONARIES: Record<Lang, Dict> = { en, bn };
