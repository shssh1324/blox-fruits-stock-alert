# Blox Fruits Stock Alert - GitHub Actions

이 프로젝트는 **내 컴퓨터가 꺼져 있어도** GitHub Actions에서 Blox Fruits Normal Stock을 주기적으로 확인하고,
원하는 열매가 새 Stock에 등장하면 Discord Webhook으로 알림을 보냅니다.

## 1. GitHub 저장소 만들기

GitHub에서 새 저장소(repository)를 만듭니다.

추천:
- 이름: `blox-fruits-stock-alert`
- Public으로 설정

Public 저장소에서 표준 GitHub-hosted runner를 사용하는 Actions 실행은 무료입니다.

## 2. 파일 업로드

이 폴더의 파일 구조를 그대로 저장소 루트에 업로드합니다.

```text
blox-fruits-stock-alert/
├─ monitor.py
├─ config.json
├─ state.json (처음에는 없어도 됨)
└─ .github/
   └─ workflows/
      └─ stock-alert.yml
```

## 3. 감시할 열매 설정

`config.json`을 수정합니다.

예:
```json
{
  "targets": [
    "Kitsune",
    "Dragon",
    "Dough"
  ]
}
```

원하는 열매를 여러 개 넣을 수 있습니다.

변경한 뒤 Commit하면 다음 예약 실행부터 적용됩니다.

## 4. Discord Webhook Secret 만들기

저장소:
Settings
→ Secrets and variables
→ Actions
→ New repository secret

이름:
`DISCORD_WEBHOOK_URL`

값:
Discord에서 만든 Webhook URL 전체

Webhook URL을 코드나 공개 파일에 넣지 마세요.

## 5. Actions 활성화

저장소의 Actions 탭으로 이동합니다.
처음에는 workflow가 비활성화되어 있다면 Enable workflow를 누릅니다.

그 다음:
Actions
→ Blox Fruits Stock Alert
→ Run workflow

를 눌러 수동으로 첫 실행을 해볼 수 있습니다.

## 6. 정상 동작 확인

실행 로그에서:

```text
Current Normal Stock: Rocket, Spin, ...
Targets: Kitsune
Matched: none
```

처럼 나오면 정상입니다.

Kitsune이 새 Stock에 들어오면:

```text
Matched: Kitsune
Discord alert sent.
```

가 표시되고 Discord로 알림이 옵니다.

## 7. 중복 알림 방지

`state.json`에 마지막으로 확인한 "Stock + 대상 설정"의 해시가 저장됩니다.
같은 Stock이 10분마다 반복 확인되어도 같은 알림을 계속 보내지 않습니다.

## 8. 중요한 GitHub Actions 제한

예약 실행은 최소 5분 간격까지 설정할 수 있지만, GitHub는 부하가 높을 때 scheduled workflow가 지연될 수 있다고 안내합니다.
또한 Public 저장소의 scheduled workflow는 저장소 활동이 60일 동안 없으면 자동 비활성화될 수 있습니다.

이 프로젝트는 10분 간격으로 예약합니다.
Blox Fruits Normal Stock은 약 4시간마다 바뀌므로 이 정도 간격이면 충분히 촘촘한 편입니다.

## 9. 주의

이 방법은 "내 컴퓨터가 꺼져 있어도 감시"할 수 있지만,
GitHub Actions의 scheduled workflow는 VPS처럼 완전한 24/7 상시 프로세스가 아닙니다.
스케줄 지연/비활성화 가능성이 있으므로 절대적인 실시간 보장은 하지 않습니다.
