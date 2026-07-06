#!/usr/bin/env python3
"""AI융합 간호정보학 데일리 뉴스 수집 스크립트.

매일 오전 6시(KST)에 GitHub Actions로 실행되어:
1. AI / IT / 간호 / 간호정보학 뉴스 RSS 피드를 병렬로 수집
2. 간호정보학 최신 논문(PubMed) 수집
3. data/news-YYYY-MM-DD.json, data/latest.json, data/archive.json 생성
"""

import json
import os
import re
import sys
import time
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d")
# 최근 48시간 이내 기사만 수집 (주말/공휴일 대비 여유)
CUTOFF = NOW - timedelta(hours=48)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

USER_AGENT = "Mozilla/5.0 (compatible; DailyAININews/1.0; +https://github.com/jp5678/Daily-AI-NI-News)"

# ---------------------------------------------------------------------------
# 뉴스 소스 정의
# category: ai(AI 뉴스) / it(IT 뉴스) / nurse(간호 뉴스) / ni(간호정보학·디지털헬스)
# 같은 피드를 두 카테고리에 등록해도 중복 제거로 기사는 한 곳에만 실린다.
# (먼저 정의된 카테고리가 우선이므로 nurse를 ni보다 앞에 둔다)
# ---------------------------------------------------------------------------
FEEDS = [
    # --- 국내 AI ---
    {"name": "AI타임스", "url": "https://www.aitimes.com/rss/allArticle.xml", "category": "ai", "lang": "ko"},
    {"name": "인공지능신문", "url": "https://www.aitimes.kr/rss/allArticle.xml", "category": "ai", "lang": "ko"},
    {"name": "THE AI", "url": "https://www.newstheai.com/rss/allArticle.xml", "category": "ai", "lang": "ko"},
    # Section902는 SW 전반을 다루므로 AI 관련 기사만 선별
    {"name": "전자신문 SW·AI", "url": "https://rss.etnews.com/Section902.xml", "category": "ai", "lang": "ko", "keywords": "ai"},
    # --- 해외 AI ---
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "ai", "lang": "en"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "ai", "lang": "en"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "ai", "lang": "en"},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/", "category": "ai", "lang": "en"},
    {"name": "Google AI 블로그", "url": "https://blog.google/technology/ai/rss/", "category": "ai", "lang": "en"},
    {"name": "OpenAI 뉴스", "url": "https://openai.com/news/rss.xml", "category": "ai", "lang": "en"},
    # --- 국내 IT ---
    {"name": "전자신문 IT", "url": "https://rss.etnews.com/Section901.xml", "category": "it", "lang": "ko"},
    {"name": "ZDNet Korea", "url": "https://feeds.feedburner.com/zdkorea", "category": "it", "lang": "ko"},
    {"name": "디지털데일리", "url": "https://www.ddaily.co.kr/rss/S1N1.xml", "category": "it", "lang": "ko"},
    {"name": "디지털투데이", "url": "https://www.digitaltoday.co.kr/rss/allArticle.xml", "category": "it", "lang": "ko"},
    {"name": "보안뉴스", "url": "https://www.boannews.com/media/news_rss.xml", "category": "it", "lang": "ko"},
    {"name": "테크월드뉴스", "url": "https://www.epnc.co.kr/rss/allArticle.xml", "category": "it", "lang": "ko"},
    # --- 해외 IT ---
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "it", "lang": "en"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "category": "it", "lang": "en"},
    {"name": "Engadget", "url": "https://www.engadget.com/rss.xml", "category": "it", "lang": "en"},
    {"name": "BBC Technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "category": "it", "lang": "en"},
    # --- 간호 뉴스 ---
    {"name": "간호사신문", "url": "https://www.nursenews.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko"},
    {"name": "간호사타임즈", "url": "https://www.fornurse.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko"},
    {"name": "간호조무사신문", "url": "https://www.klpnnews.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko"},
    {"name": "병원신문", "url": "https://www.khanews.com/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "라포르시안", "url": "https://www.rapportian.com/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "의학신문", "url": "http://www.bosa.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "메디칼타임즈", "url": "https://www.medicaltimes.com/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "데일리메디", "url": "https://www.dailymedi.com/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "청년의사", "url": "https://www.docdocdoc.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "헬스코리아뉴스", "url": "https://www.hkn24.com/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "메디컬옵저버", "url": "https://www.monews.co.kr/rss/allArticle.xml", "category": "nurse", "lang": "ko", "keywords": "nurse"},
    {"name": "Nursing Times", "url": "https://www.nursingtimes.net/feed/", "category": "nurse", "lang": "en"},
    {"name": "American Nurse Journal", "url": "https://www.myamericannurse.com/feed/", "category": "nurse", "lang": "en"},
    {"name": "Daily Nurse", "url": "https://dailynurse.com/feed/", "category": "nurse", "lang": "en"},
    {"name": "Nurse.com", "url": "https://www.nurse.com/blog/feed/", "category": "nurse", "lang": "en"},
    # --- 보건의료·간호 (국내) ---
    {"name": "메디칼타임즈", "url": "https://www.medicaltimes.com/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    {"name": "데일리메디", "url": "https://www.dailymedi.com/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    {"name": "청년의사", "url": "https://www.docdocdoc.co.kr/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    {"name": "히트뉴스", "url": "https://www.hitnews.co.kr/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    {"name": "후생신보", "url": "https://www.whosaeng.com/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    {"name": "메디파나뉴스", "url": "https://www.medipana.com/rss/allArticle.xml", "category": "ni", "lang": "ko"},
    # --- 디지털헬스·간호정보학 (해외) ---
    {"name": "Healthcare IT News", "url": "https://www.healthcareitnews.com/home/feed", "category": "ni", "lang": "en"},
    {"name": "MobiHealthNews", "url": "https://www.mobihealthnews.com/feed", "category": "ni", "lang": "en"},
    {"name": "HIMSS News", "url": "https://www.himss.org/news/rss.xml", "category": "ni", "lang": "en"},
    {"name": "Digital Health News", "url": "https://www.digitalhealth.net/feed/", "category": "ni", "lang": "en"},
    {"name": "Fierce Healthcare", "url": "https://www.fiercehealthcare.com/rss/xml", "category": "ni", "lang": "en", "keywords": "ni"},
    {"name": "MedCity News", "url": "https://medcitynews.com/feed/", "category": "ni", "lang": "en", "keywords": "ni"},
    {"name": "HIStalk", "url": "https://histalk2.com/feed/", "category": "ni", "lang": "en"},
]

# 간호정보학 카테고리(ni)에서 의료 일반 기사 중 관련 기사를 골라내는 키워드
NI_KEYWORDS = [
    # 한국어
    "간호정보", "간호사", "간호", "전자의무기록", "전자건강기록", "의료정보", "보건의료정보",
    "디지털헬스", "디지털 헬스", "스마트병원", "원격의료", "원격진료", "비대면진료", "의료AI",
    "의료 AI", "인공지능", "빅데이터", "마이데이터", "웨어러블", "환자안전", "임상의사결정",
    "EMR", "EHR", "PHR", "CDSS", "디지털치료", "보건의료데이터", "의료데이터", "간호대학",
    "간호교육", "널싱", "요양", "돌봄로봇", "케어",
    # 영어
    "nursing", "nurse", "informatics", "ehr", "emr", "electronic health record",
    "clinical decision support", "patient safety", "telehealth", "telemedicine",
    "digital health", "health it", "artificial intelligence", " ai ", "ai-",
    "machine learning", "wearable", "remote monitoring", "interoperability",
    "fhir", "documentation", "workflow", "burnout", "virtual care", "chatbot",
    "generative", "llm", "clinical", "hospital",
]

# 피드에 "keywords": "ai" 지정 시 아래 키워드가 포함된 기사만 수집
AI_KEYWORDS = [
    "인공지능", " ai", "ai ", "에이아이", "생성형", "챗gpt", "챗봇", "거대언어모델",
    "llm", "머신러닝", "딥러닝", "신경망", "오픈ai", "앤트로픽", "제미나이", "코파일럿",
    "에이전트", "추론 모델", "파운데이션 모델", "지능형",
]

# 간호 뉴스 선별 키워드 (의료 일반 매체용)
NURSE_KEYWORDS = [
    "간호", "널스", "간협", "조산사", "요양보호", "보건교사",
    "nurse", "nursing", "midwife",
]

KEYWORD_SETS = {"ai": AI_KEYWORDS, "ni": NI_KEYWORDS, "nurse": NURSE_KEYWORDS}

MAX_PER_SOURCE = 6
MAX_PER_CATEGORY = 20
MAX_PAPERS = 10

# 피드를 동시에 받아오는 스레드 수 (피드가 많아 순차 수집은 느리다)
FETCH_WORKERS = 8
FETCH_TIMEOUT = 15
FETCH_RETRIES = 1


def log(msg):
    print(f"[fetch_news] {msg}", file=sys.stderr)


def fetch_url(url, timeout=FETCH_TIMEOUT, retries=FETCH_RETRIES):
    """URL을 받아 bytes 반환. 일시적 네트워크 오류는 짧은 백오프 후 재시도."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    """RSS/Atom의 다양한 날짜 형식을 KST datetime으로 변환."""
    if not value:
        return None
    value = value.strip()
    try:
        return parsedate_to_datetime(value).astimezone(KST)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return dt.astimezone(KST)
        except Exception:
            continue
    return None


def _findtext(el, names):
    """네임스페이스 유무와 무관하게 첫 매칭 자식 텍스트를 반환."""
    for child in el.iter():
        tag = child.tag.split("}")[-1].lower()
        if tag in names and child is not el:
            if child.text and child.text.strip():
                return child.text.strip()
    return None


def parse_feed(xml_bytes):
    """RSS 2.0 / Atom 피드를 파싱해 항목 리스트 반환."""
    # 잘못된 문자 제거 후 파싱
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    root = ET.fromstring(text)

    items = []
    # RSS: channel/item, Atom: entry
    nodes = root.findall(".//item")
    if not nodes:
        nodes = [el for el in root.iter() if el.tag.split("}")[-1] == "entry"]

    for node in nodes:
        title = _findtext(node, {"title"})
        link = _findtext(node, {"link", "guid"})
        # Atom은 link가 href 속성에 있음
        if not link or not link.startswith("http"):
            for child in node.iter():
                if child.tag.split("}")[-1] == "link" and child.get("href"):
                    link = child.get("href")
                    break
        desc = _findtext(node, {"description", "summary", "content", "encoded"})
        pub = _findtext(node, {"pubdate", "published", "updated", "date", "dc:date"})
        if not title or not link:
            continue
        items.append({
            "title": strip_html(title),
            "link": link.strip(),
            "summary": strip_html(desc)[:300] if desc else "",
            "published": parse_date(pub),
        })
    return items


def matches_keywords(item, keywords):
    text = f" {item['title']} {item['summary']} ".lower()
    return any(kw in text for kw in keywords)


def _fetch_feed(feed):
    """피드를 받아 파싱한 (feed, items) 튜플 반환. 실패 시 items=None."""
    try:
        return feed, parse_feed(fetch_url(feed["url"]))
    except Exception as e:
        log(f"SKIP {feed['name']}: {e}")
        return feed, None


def collect_feeds():
    articles = {"ai": [], "it": [], "nurse": [], "ni": []}
    seen_links = set()
    seen_titles = set()

    # 모든 피드를 병렬로 받되, 중복 제거는 FEEDS 정의 순서대로 처리해
    # 카테고리 우선순위(nurse가 ni보다 먼저)를 그대로 유지한다.
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        results = list(executor.map(_fetch_feed, FEEDS))

    for feed, items in results:
        if items is None:
            continue

        count = 0
        for item in items:
            if count >= MAX_PER_SOURCE:
                break
            if item["published"] and item["published"] < CUTOFF:
                continue
            key = item["link"].split("?")[0].rstrip("/")
            title_key = re.sub(r"\W+", "", item["title"].lower())[:60]
            if key in seen_links or title_key in seen_titles:
                continue
            # 피드별 키워드 필터 (ni 국문 매체는 기본으로 간호정보학 키워드 적용)
            kw_set = feed.get("keywords")
            if not kw_set and feed["category"] == "ni" and feed["lang"] == "ko":
                kw_set = "ni"
            if kw_set and not matches_keywords(item, KEYWORD_SETS[kw_set]):
                continue
            seen_links.add(key)
            seen_titles.add(title_key)
            articles[feed["category"]].append({
                "title": item["title"],
                "link": item["link"],
                "summary": item["summary"],
                "source": feed["name"],
                "lang": feed["lang"],
                "published": item["published"].isoformat() if item["published"] else None,
            })
            count += 1
        log(f"OK {feed['name']}: {count} articles")

    # 최신순 정렬 후 카테고리별 상한 적용
    for cat in articles:
        articles[cat].sort(key=lambda a: a["published"] or "", reverse=True)
        articles[cat] = articles[cat][:MAX_PER_CATEGORY]
    return articles


def collect_pubmed_papers():
    """PubMed E-utilities로 최근 간호정보학 논문 수집 (API 키 불필요)."""
    query = (
        '("nursing informatics"[Title/Abstract] OR '
        '("artificial intelligence"[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '("machine learning"[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '("large language model*"[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '("digital health"[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '(telehealth[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '("clinical decision support"[Title/Abstract] AND nurs*[Title/Abstract]) OR '
        '("electronic health record*"[Title/Abstract] AND nurs*[Title/Abstract]))'
    )
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    tool = "&tool=DailyAININews"
    try:
        search_url = (
            f"{base}/esearch.fcgi?db=pubmed&retmode=json&retmax={MAX_PAPERS}"
            f"&sort=date&datetype=edat&reldate=14{tool}&term={urllib.parse.quote(query)}"
        )
        ids = json.loads(fetch_url(search_url))["esearchresult"].get("idlist", [])
        if not ids:
            return []
        summary_url = f"{base}/esummary.fcgi?db=pubmed&retmode=json{tool}&id={','.join(ids)}"
        result = json.loads(fetch_url(summary_url))["result"]
        papers = []
        for pmid in ids:
            doc = result.get(pmid)
            if not doc:
                continue
            authors = [a.get("name", "") for a in doc.get("authors", [])[:3]]
            papers.append({
                "title": strip_html(doc.get("title", "")),
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "journal": doc.get("fulljournalname", "") or doc.get("source", ""),
                "authors": ", ".join(a for a in authors if a) + (" 외" if len(doc.get("authors", [])) > 3 else ""),
                "pubdate": doc.get("epubdate") or doc.get("pubdate", ""),
            })
        log(f"OK PubMed: {len(papers)} papers")
        return papers
    except Exception as e:
        log(f"SKIP PubMed: {e}")
        return []


def load_previous_latest():
    path = os.path.join(DATA_DIR, "latest.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    articles = collect_feeds()
    papers = collect_pubmed_papers()

    total = sum(len(v) for v in articles.values())
    log(f"Total articles: {total}, papers: {len(papers)}")

    # 수집이 완전히 실패하면 이전 데이터를 유지 (빈 페이지 방지)
    if total == 0 and not papers:
        prev = load_previous_latest()
        if prev:
            log("All sources failed; keeping previous data.")
            return
        log("All sources failed and no previous data; writing empty payload.")

    payload = {
        "date": TODAY,
        "generatedAt": NOW.isoformat(),
        "articles": articles,
        "papers": papers,
    }

    daily_path = os.path.join(DATA_DIR, f"news-{TODAY}.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # 아카이브 인덱스 갱신 (최근 30일 유지)
    archive_path = os.path.join(DATA_DIR, "archive.json")
    dates = sorted(
        fn[5:-5] for fn in os.listdir(DATA_DIR)
        if re.fullmatch(r"news-\d{4}-\d{2}-\d{2}\.json", fn)
    )
    for old in dates[:-30]:
        os.remove(os.path.join(DATA_DIR, f"news-{old}.json"))
    dates = dates[-30:]
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump({"dates": list(reversed(dates))}, f, ensure_ascii=False, indent=1)

    log(f"Wrote {daily_path}")


if __name__ == "__main__":
    main()
