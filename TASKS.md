# WIZnet S2E Tool GUI — 작업 목록

> 브랜치: `dev/feat-fw-from-git` | 버전: `1.6.2.1-dev` | 갱신: 2026-05-08

---

## 🔴 P0 — 즉시 처리 가능

- [ ] `dev/refactor3` → master merge + v1.6.1.1 정식 릴리즈
- [ ] Wiki v1.6.1 업데이트 (현재 v1.5.9 기준)

---

## 🟠 P1 — 기능 영향 버그 (메인 프로젝트)

- [ ] BOOT 상태 시 Apply GUI 미차단 — `main_gui.py:4160`
- [ ] `ch2_baud` (EB) 2채널 baudrate 목록 관리 개선 — `main_gui.py:1488`

---

## 🟡 P2 — 코드 품질 (메인 프로젝트)

- [ ] U3~U9 주석 블록 삭제 (dead code) — `main_gui.py:825`
- [ ] `WIZMakeCMD` device profile 적용 미완성 — `WIZMakeCMD.py:335`
- [ ] `version_compare_old()` 자릿수 비교 버그 — `WIZMakeCMD.py:143`

---

## 🟡 P1 — refactored/ 미완성

- [ ] BUG-003: Apply 후 `int("")` 크래시 — `main.py _on_set_response()`
- [ ] L-001: WIZ752SR-125 채널1(EB, ED, EP) Inspector 미지원
- [ ] L-002: FW 업로드 미구현
- [ ] BUG-001: FlowCanvas SERIAL 노드 "19 bps" 잘못 표시
- [ ] Inspector `_GROUP_TITLES` 11개 그룹 미정의

---

## 🟢 P2 — refactored/ 개선

- [ ] BUG-002: 테마 전환 시 인라인 `setStyleSheet` 위젯 색상 미반영
- [ ] L-005: `_on_nic_changed()` 소켓 재생성 미구현

---

## 🔵 차기 마일스톤 FEATURE

- [ ] Dashboard 탭 — AWS OTA 링크 버튼 (URL 확정 대기)
- [ ] 테스트 탭 — TCP Client/Server / UDP / MQTT 브로커 / UART 송수신
- [ ] 다중 장비 선택 + 일괄 명령
- [ ] 웹 UI 제공 (설계 미정)
- [ ] FW 파일 종류 근본 구별 (APP/BOOT 헤더 분석)
- [x] Help/About → GitHub Release 링크 + FF 방식 버전 체크 ✅ `c3af885`

---

## ⏸ 테스트 보류 (장비/재현 불가)

- [ ] 2대 이상 동시 검색 멀티패킷 (장비 부족)
- [ ] FW 업로드 정상 흐름 (이미지 파일 없음)
- [ ] FW 비정상 응답 처리 (재현 불가)
- [ ] 손상된 IMIN 응답 처리 (재현 불가)

---

## 🔬 조사 필요

- [ ] 시작 딜레이 개선 — `ifaddr` ctypes 대체 + splash screen
  → `research/2026-04-17-startup-bottleneck-analysis.md`
