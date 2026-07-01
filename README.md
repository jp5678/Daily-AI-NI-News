# AI융합 간호정보학 데일리 뉴스 📰

AI융합 간호정보학 수강생을 위해 **매일 오전 6시(KST)** 최신 AI · IT · 간호정보학 뉴스와
최신 논문을 자동으로 수집해 보여주는 웹 플랫폼입니다.

## 작동 방식

```
매일 06:00 KST (GitHub Actions cron)
   └─ scripts/fetch_news.py 실행
        ├─ 국내·해외 AI/IT 뉴스 RSS 수집 (AI타임스, 전자신문, TechCrunch 등)
        ├─ 보건의료·디지털헬스 뉴스 수집 (메디칼타임즈, Healthcare IT News 등)
        ├─ PubMed에서 간호정보학 최신 논문 수집
        └─ data/latest.json + data/news-YYYY-MM-DD.json 생성 후 커밋
   └─ GitHub Pages가 index.html을 서빙 → 학생들이 접속해서 열람
```

- **뉴스 수집**: 공개 RSS 피드 + PubMed E-utilities API (API 키 불필요)
- **아카이브**: 최근 30일치 브리핑을 날짜별로 다시 볼 수 있음
- **비용**: GitHub 무료 플랜으로 완전 무료 운영

## 최초 설정 (한 번만)

1. 이 브랜치를 기본 브랜치(main)에 병합합니다.
2. 저장소 **Settings → Pages**에서 Source를 `Deploy from a branch`,
   Branch를 `main` / `(root)`로 설정합니다.
3. **Actions 탭 → Daily News Update → Run workflow**를 눌러 첫 뉴스 수집을 실행합니다.
   (이후에는 매일 오전 6시에 자동 실행됩니다.)
4. 발급된 주소(`https://<계정명>.github.io/Daily-AI-NI-News/`)를 수강생에게 공유합니다.

> 참고: GitHub Actions의 스케줄 실행은 부하에 따라 몇 분~수십 분 지연될 수 있습니다.

## 뉴스 소스 수정하기

`scripts/fetch_news.py` 상단의 `FEEDS` 목록에서 RSS 피드를 추가/삭제할 수 있습니다.

```python
{"name": "매체명", "url": "https://.../rss.xml", "category": "ai|it|nurse|ni", "lang": "ko|en"}
```

- `category`: `ai`(AI 뉴스) / `it`(IT 뉴스) / `nurse`(간호 뉴스) / `ni`(간호정보학·디지털헬스)
- 국내 의료 매체(`ni` + `ko`)는 간호·디지털헬스 관련 키워드가 포함된 기사만 선별됩니다.
  키워드는 같은 파일의 `NI_KEYWORDS`에서 조정하세요.

## 로컬 테스트

```bash
python scripts/fetch_news.py   # data/ 폴더에 JSON 생성
python -m http.server 8000     # http://localhost:8000 접속
```
