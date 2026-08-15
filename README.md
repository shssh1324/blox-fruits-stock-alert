# Blox Fruits Stock Alert - GitHub Actions v2

이 버전은 GitHub Actions에서 RBX Planet 요청이 일시적으로 timeout되는 경우를 대비한 수정판입니다.

- RBX Planet 요청 최대 4회 재시도
- 요청 제한시간 35초
- 재시도 사이 대기
- RBX Planet 실패 시 기존 공개 API를 보조로 시도
- 두 소스 모두 실패해도 그 실행만 WARNING으로 종료하고 다음 예약 실행에서 재시도
- actions/checkout@v5 사용

## 적용
기존 저장소에서:
- `monitor.py`를 이 버전으로 교체
- `.github/workflows/stock-alert.yml`를 이 버전으로 교체
- `config.json`은 기존 것을 유지하거나 원하는 열매로 수정

## 자동 실행
매 10분:
07, 17, 27, 37, 47, 57분 UTC
한국 시간:
06, 16, 26, 36, 46, 56분

## Discord
Settings → Secrets and variables → Actions
`DISCORD_WEBHOOK_URL` secret에 Webhook URL을 저장합니다.

## 정상 로그
Current Normal Stock: ...
Matched: none
또는
Matched: Kitsune
Discord alert sent.

## 일시 장애 로그
WARNING: Stock check could not be completed.
...
다음 예약 실행에서 다시 시도합니다.
