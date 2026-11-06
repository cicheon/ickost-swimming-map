# ICKOST 바다수영 지도

기존 Flask 화면을 유지하면서 메인 지도 배경을 OpenStreetMap으로 복구하고,
홈 + 33개 상세 페이지를 정적 HTML로 생성합니다. 방문 시 Python 서버나 YouTube API가 필요하지 않습니다.

## 로컬 실행

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python build_static.py
python -m http.server 8000 --directory dist
```

`http://localhost:8000/`에서 확인합니다. 기존 Railway용 `Procfile`도 유지합니다.
장소·경로·영상은 기존처럼 `ickost_final.py`의 `SPOT_DATA`를 수정합니다.

## Cloudflare Pages: 가장 간단한 배포

1. Cloudflare에서 Workers & Pages → Pages → Git 저장소 연결을 선택합니다.
2. 이 저장소와 `main` 브랜치를 선택합니다.
3. Framework preset: None, 빌드 명령: `pip install -r requirements.txt && python build_static.py`, 출력 디렉터리: `dist`.
4. 빌드 환경변수 `PYTHON_VERSION=3.11`을 지정합니다. YouTube 정보를 표시하려면 `YOUTUBE_API_KEY`를 비밀 환경변수로 설정합니다. `CHANNEL_ID`는 생략하면 기존 채널을 사용합니다.
5. 배포 후 제공되는 `*.pages.dev` 주소에서 홈·상세·지도를 확인합니다.

이 방식은 Git push 때 갱신합니다. GitHub Actions의 예약 실행은 별개이며, 아래 직접 배포 설정 없이는 Cloudflare 페이지를 갱신하지 않습니다.

## 매일 자동 갱신하려면 (선택)

Git 연동 방식 대신 Cloudflare **Direct Upload** Pages 프로젝트를 만들고 GitHub Actions를 배포 경로로 사용합니다.
기존 Git 연동 프로젝트는 Direct Upload 프로젝트로 전환할 수 없으므로 처음부터 한 방식을 선택하세요.

저장소 Settings → Secrets and variables → Actions에 설정합니다.

- Secrets: `YOUTUBE_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- Variables: `CLOUDFLARE_PROJECT_NAME` (생성한 Pages 프로젝트 이름), 선택적으로 `CHANNEL_ID`

Cloudflare 토큰은 해당 계정의 Pages 배포에 필요한 최소 권한으로 발급합니다.
워크플로는 main push, 수동 실행, 매일 한국시간 06:17에 빌드·배포합니다.
GitHub 예약 실행은 지연될 수 있고, 공개 저장소의 장기간 비활동 시 비활성화될 수 있습니다.
Cloudflare 설정이 없으면 빌드 결과만 Actions artifact로 저장합니다.
PR에서는 배포하지 않으며, 외부 fork PR에는 API secret이 전달되지 않습니다.

## YouTube 정보와 지도

- 영상 ID를 중복 제거하고 최대 50개씩 조회합니다. 현재 데이터는 영상 2회 + 채널 1회 요청으로 갱신할 수 있습니다.
- `.youtube-cache.json`에는 공개 메타데이터만 저장하며 API 키는 저장하지 않습니다. GitHub Actions는 이를 다음 빌드에 재사용합니다.
- API 키가 없거나 호출이 실패하면 캐시를 사용합니다. 캐시도 없으면 `—` / `정보 없음`으로 표시합니다. 임의의 조회수·날짜를 표시하지 않습니다.
- Cloudflare Git 연동 빌드에서는 이 로컬 캐시의 빌드 간 유지가 보장되지 않습니다.
- OpenStreetMap 출처 표기를 유지합니다. 표준 타일은 무제한 상업 서비스가 아니며 대량 다운로드·미리 가져오기 없이 사용해야 합니다.
  정책: https://operations.osmfoundation.org/policies/tiles/
- 정적 페이지에도 외부 지도 타일, CDN, YouTube 썸네일을 위한 인터넷 연결은 필요합니다.

## 이전 마무리

새 주소에서 동작을 검증하고 공유 링크를 교체한 뒤 Railway 서비스와 과금 항목을 직접 정리합니다.
`up.railway.app` 주소는 Cloudflare로 이전할 수 없습니다. 기존 사용자에게 새 주소를 안내하세요.
이 저장소 변경 자체는 Railway 서비스를 삭제하거나 구독을 해지하지 않습니다.
