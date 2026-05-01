# 의사과학자 키워드 모니터링

2개 의료 뉴스 사이트(청년의사 · 의협신문)에서 **'의사과학자'** 키워드가 포함된 기사를 자동 감지하고, Gmail 이메일 알림과 CSV 아카이브를 수행하는 Python 자동화 도구입니다.

---

## 파일 구조

```
kypsn-news/
├── monitor.py              # 크롤링·감지·알림·저장 핵심 로직
├── config.py               # 설정값 (사이트, 키워드, 이메일 등)
├── news_archive.csv        # 발견된 기사 누적 저장 (자동 생성)
├── monitor.log             # 실행 로그 (자동 생성)
└── .github/
    └── workflows/
        └── monitor.yml     # GitHub Actions 자동 실행 워크플로우
```

---

## 1. 설치

Python 3.10 이상이 필요합니다.

```bash
pip install requests beautifulsoup4
```

---

## 2. Gmail 앱 비밀번호 발급

일반 Gmail 비밀번호는 사용할 수 없습니다. **앱 비밀번호**를 별도로 발급해야 합니다.

1. Google 계정 → **보안** 탭 이동
   - https://myaccount.google.com/security
2. **2단계 인증**이 켜져 있는지 확인 (필수 조건)
3. 검색창에 **"앱 비밀번호"** 입력 후 이동
4. 앱 선택: **기타(직접 입력)** → `의사과학자 모니터` 입력
5. **생성** 클릭 → 16자리 비밀번호 복사 (다시 볼 수 없으니 즉시 저장)

---

## 3. 로컬 테스트 실행

### 환경변수 설정 (Windows PowerShell)

```powershell
$env:GMAIL_ADDRESS      = "your_gmail@gmail.com"
$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"   # 앱 비밀번호 (공백 포함)
$env:NOTIFY_EMAIL       = "receiver@example.com"
```

### Dry-run 테스트 (이메일 미발송, 로그만 출력)

```bash
python monitor.py --dry-run
```

### 실제 실행 (이메일 발송 포함)

```bash
python monitor.py
```

실행 후 `news_archive.csv`와 `monitor.log` 파일이 생성됩니다.

---

## 4. GitHub Actions 자동화 설정

### 4-1. GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름          | 값                              |
|----------------------|---------------------------------|
| `GMAIL_ADDRESS`      | 발신 Gmail 주소                  |
| `GMAIL_APP_PASSWORD` | 2단계에서 발급한 앱 비밀번호      |
| `NOTIFY_EMAIL`       | 알림 수신 이메일 주소             |

### 4-2. 저장소에 파일 업로드

```bash
git init
git add .
git commit -m "init: 의사과학자 모니터링 시스템"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 4-3. Actions 권한 설정

저장소 → **Settings** → **Actions** → **General** → **Workflow permissions**  
→ **Read and write permissions** 선택 후 저장

### 4-4. 자동 실행 확인

- 매일 **오전 9시 KST** 자동 실행 (UTC 00:00)
- 수동 실행: **Actions** 탭 → `의사과학자 키워드 모니터링` → **Run workflow**

---

## 5. 키워드 추가/변경

`config.py`의 `KEYWORDS` 리스트를 수정합니다.

```python
KEYWORDS = ["의사과학자", "physician scientist", "의과학자"]
```

---

## 6. 수집 범위 조정

`config.py`의 각 사이트 `pages` 값을 조정합니다 (HTML 파싱 사이트만 해당).

```python
"pages": 5   # 5페이지까지 수집
```

---

## 출력 예시

### 이메일 알림

```
제목: [의사과학자 알림] 의사과학자 육성 예산 2배 확대 추진

사이트명  : 의협신문
기사 제목 : 의사과학자 육성 예산 2배 확대 추진
URL       : https://www.doctorsnews.co.kr/news/articleView.html?idxno=12345
발견 시각 : 2026-05-01 09:03:22
```

### news_archive.csv

```csv
사이트명,기사제목,URL,발견날짜
의협신문,의사과학자 육성 예산 2배 확대 추진,https://...,2026-05-01 09:03:22
청년의사,의사과학자 제도 개편 논의 본격화,https://...,2026-05-02 09:01:45
```
