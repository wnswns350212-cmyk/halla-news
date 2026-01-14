import requests
import re
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import random
from flask import Flask, request, render_template_string

# Flask 애플리케이션 객체 생성
app = Flask(__name__)

# 네이버 API 환경변수
NAVER_CLIENT_ID = "WGtLsHz1E7932kkdcRIv"
NAVER_CLIENT_SECRET = "umH3D8r9Hl"

def normalize_title(title):
    title = re.sub(r"<.*?>", "", title)
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip().lower()

def title_core_key(title):
    title = re.sub(r"<.*?>", "", title)
    title = re.sub(r"[^\w\s]", " ", title)
    words = title.split()

    stopwords = {
        "및", "과", "와", "의", "를", "을", "에", "에서",
        "대한", "관련", "승인", "추진", "협약"
    }

    core = [w for w in words if len(w) >= 2 and w not in stopwords]
    return " ".join(core[:5]).lower()

def extract_press_name(url):
    try:
        domain = urlparse(url).netloc.replace("www.", "")
        return domain.split(".")[0]
    except:
        return "언론사"

def contains_jeju(text):
    return "제주" in text

# 네이버 뉴스 검색
def naver_news_search(query, display=50):
    if not query.strip():
        query = "대학 입시 교육"  # 기본 검색어를 더 넓은 키워드로 변경

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "date"}

    res = requests.get(url, headers=headers, params=params)
    if res.status_code != 200:
        return []

    items = res.json().get("items", [])
    results = []

    for item in items:
        try:
            pub_dt = parsedate_to_datetime(item["pubDate"])
            pub_date = pub_dt.strftime("%Y-%m-%d %H:%M")
        except:
            pub_date = item["pubDate"]

        results.append({
            "title": item["title"],
            "norm_title": normalize_title(item["title"]),
            "core_key": title_core_key(item["title"]),
            "link": item["link"],
            "press": extract_press_name(item.get("originallink", "")),
            "description": item.get("description", ""),
            "pubDate": pub_date
        })

    return results

# 언론보도스크랩
def press_scrap_search(query):
    raw_list = naver_news_search(query, display=50)

    education_keywords = [
        "대학", "입시", "수시", "정시", "교육",
        "신입생", "모집", "학과", "캠퍼스",
        "총장", "혁신", "사업", "국책", "지원"
    ]

    # ❌ 차단 키워드 (확장)
    blacklist_keywords = [
        # 기존
        "현역가왕", "kbo", "야구", "프로야구",
        "oled", "반도체", "디스플레이",
        "국회의원", "정치", "총선",
        "코스피", "코스닥", "주식", "증시",
        "마약", "도박", "연예", "아이돌", "드라마",

        # ✅ 해외 관련
        "해외", "외국", "미국", "중국", "일본",
        "유럽", "글로벌", "국제", "world", "global",

        # ✅ 음악 관련
        "음악", "가수", "콘서트", "공연",
        "앨범", "싱글", "뮤직", "노래"
    ]

    seen_links = set()
    seen_titles = set()
    seen_cores = set()
    results = []

    for news in raw_list:
        text = (news["title"] + news["description"]).lower()

        if any(b in text for b in blacklist_keywords):
            continue

        if not any(k in text for k in education_keywords):
            continue

        if news["link"] in seen_links:
            continue
        if news["norm_title"] in seen_titles:
            continue
        if news["core_key"] in seen_cores:
            continue

        seen_links.add(news["link"])
        seen_titles.add(news["norm_title"])
        seen_cores.add(news["core_key"])
        results.append(news)

    return results

# 메인
@app.route("/")
def index():
    base_query = request.args.get("q", "").strip() or "대학 입시 교육"
    halla = request.args.get("halla", "0") == "1"
    press = request.args.get("press", "0") == "1"
    category = request.args.get("cat", "")

    category_keywords = {
        "입시": ["입시", "수시", "정시", "모집"],
        "대학혁신": ["혁신", "사업", "지원"],
        "사업": ["국책", "정부", "지원"],
        "대학생활": ["학생", "캠퍼스", "축제"]
    }

    search_query = base_query

    if halla and not press:
        search_query += " 한라대학교"

    if category in category_keywords and not press:
        search_query += " " + random.choice(category_keywords[category])

    if press:
        news_list = press_scrap_search(base_query)
        mode_title = "📌 언론보도스크랩"
    else:
        news_list = naver_news_search(search_query)
        mode_title = "전체 대학 뉴스"

    # 제주 필터
    allow_jeju = "제주한라대학교" in base_query or "제주 한라대학교" in base_query
    filtered = []

    for n in news_list:
        text = n["title"] + n["description"]
        if contains_jeju(text) and not allow_jeju:
            continue
        filtered.append(n)

    news_list = filtered

    html = """
    <!doctype html>
    <html lang="ko">
    <head>
    <meta charset="utf-8">
    <title>한라대 대학 뉴스 정리</title>
    <style>
    body { font-family: Arial; margin:30px; background:#f3f4f6; }
    .panel, .search-box { background:#fff; padding:16px; border-radius:8px; margin-bottom:20px; }
    .btn { padding:8px 14px; margin-right:6px; border:1px solid #ccc; border-radius:6px; text-decoration:none; color:#000; }
    .btn.active { background:#2563eb; color:#fff; }
    .news { background:#fff; padding:14px; border-radius:8px; margin-bottom:14px; }
    .press-name { color:#2563eb; font-weight:bold; font-size:13px; }
    .date { font-size:13px; color:#666; }
    </style>
    </head>
    <body>

    <h1>한라대 대학 뉴스 정리</h1>
    <div>{{ mode_title }}</div>

    <div class="search-box">
    <form>
    <input name="q" value="{{ base_query }}">
    <input type="hidden" name="halla" value="{{ 1 if halla else 0 }}">
    <input type="hidden" name="press" value="{{ 1 if press else 0 }}">
    <input type="hidden" name="cat" value="{{ category }}">
    <button>검색</button>
    </form>
    </div>

    <div class="panel">
    <a class="btn {{ 'active' if halla else '' }}" href="/?q={{ base_query }}&halla={{ 0 if halla else 1 }}&press={{ press|int }}&cat={{ category }}">한라대학교</a>
    <a class="btn {{ 'active' if press else '' }}" href="/?q={{ base_query }}&press={{ 0 if press else 1 }}&halla={{ halla|int }}&cat={{ category }}">언론보도스크랩</a>
    </div>

    <div class="panel">
    <b>카테고리</b><br><br>
    {% for c in ['입시','대학혁신','사업','대학생활'] %}
    <a class="btn {{ 'active' if category==c else '' }}"
       href="/?q={{ base_query }}&cat={{ '' if category==c else c }}&halla={{ halla|int }}&press={{ press|int }}">
    {{ c }}</a>
    {% endfor %}
    </div>

    {% for n in news_list %}
    <div class="news">
    <div class="press-name">[{{ n.press }}]</div>
    <a href="{{ n.link }}" target="_blank"><b>{{ n.title | safe }}</b></a>
    <div class="date">{{ n.pubDate }}</div>
    <div>{{ n.description | safe }}</div>
    </div>
    {% endfor %}

    {% if not news_list %}
    <p>표시할 뉴스가 없습니다.</p>
    {% endif %}

    </body>
    </html>
    """

    return render_template_string(
        html,
        news_list=news_list,
        base_query=base_query,
        halla=halla,
        press=press,
        category=category,
        mode_title=mode_title
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
