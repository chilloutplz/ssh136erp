# ssh136erp — 프로젝트 가이드

## 프로젝트 개요

- 숙성회136 (인천 송도) 단일 매장을 위한 풀스택 ERP
- 1차 목적: matepos → tosspos로 이어지는 두 POS 시스템의 매출 데이터를 하나의 스키마로 통합
- 향후: 구매 / 원가 / BOM 관리로 확장 예정

## 스택

- Backend: Django 6.1 + DRF + PostgreSQL(운영) / SQLite(로컬)
  - `djangorestframework-simplejwt`, `django-cors-headers`, `python-decouple`
- Frontend: Vue3 + Vite
- 배포: GitHub → cloudtype (backend / frontend 별도 서비스)
- Monorepo 구조: `backend/`, `frontend/`, `delivery-collectors/`

## 관련 문서

- @REQUIREMENTS.md — 요구사항, 데이터 모델, Phase별 범위
- @TASKS.md — 지금 해야 할 일 체크리스트
- @backend/integrations/tosspos/API_NOTES.md — tosspos Open API 필드/enum 참조 (source, orderState, diningOption, paymentMethod 등). tosspos 관련 필드값을 다룰 때는 이 파일부터 확인할 것

## 절대 규칙 (Hard Rules)

1. **환경변수는 반드시 `python-decouple`의 `config()`를 사용한다.** `os.getenv()` 사용 금지 — Django `.env` 로딩 방식과 호환되지 않아 과거 문제가 있었음.
2. **cloudtype이 이미 수정해둔 `settings.py` 항목을 임의로 덮어쓰지 않는다.** (whitenoise, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`) 이 부분을 건드려야 할 때는 반드시 먼저 확인받는다.
3. **파일을 전달할 때는 항상 전체 경로 + 변경 내역을 명시한다.** zip 통짜 전달 금지, 경로 없이 부분만 전달하는 것도 금지. (과거 `sales/urls.py` 누락으로 404 사고 발생한 적 있음)
4. **현재 Phase 범위를 벗어난 기능을 먼저 구현하지 않는다.** 다음 Phase 작업이 필요해 보여도 먼저 확인 후 진행한다.
5. **필요한 정보는 추측하지 말고 반드시 질문한다.** 특히 매장 운영 규칙, 외부 API 인증 스킴, 금액 필드의 정확한 의미 등.
6. **새로운 기능은 항상 실제 작업자 또는 도구명(예: Manus, Claude, Codex, Grok)과 새 브랜치를 명시하여 작업한다.** 작업자는 특정 도구로 한정하지 않으며, 실제 사용한 작업자 또는 도구명을 기록한다. `main` 브랜치에서 직접 작업하거나 직접 커밋하지 않으며, 작업 브랜치에서 검토·검증을 마친 뒤에만 별도 절차로 `main` 반영을 진행한다.

## 코드 컨벤션

- 통합 매출 스키마는 `Sale` – `SaleItem` – `SaleTender` 3단 구조를 기준으로 한다. (matepos의 `map_sale` / `map_item` / `map_tender` 필드 체계를 그대로 계승)
- 신규 POS·배달앱 연동 시에도 반드시 동일 스키마에 매핑해서 저장한다.
- 원본 payload는 항상 `raw_data` JSONField에 그대로 보관한다. (추후 재계산·보정 대비)

## 실행 명령어

```bash
# Backend
cd backend
./venv/bin/python manage.py runserver

# Frontend
cd frontend
npm run dev

# matepos 백필 (dry-run 먼저 실행 권장)
python manage.py backfill_matepos --start YYYYMMDD --end YYYYMMDD --dry-run

# tosspos 백필
python manage.py backfill_tosspos --start YYYYMMDD --end YYYYMMDD --dry-run
```

## 문서 분리 기준

- 이 파일이 300줄을 넘거나, 특정 주제가 5개 이상 쌓이면 별도 파일로 분리한다.
- 분리 후보:
  - 설계 결정과 그 배경("왜 이렇게 했는가")이 쌓이면 → `.claude/DECISIONS.md`
  - 배포/장애 대응 절차가 쌓이면 → `.claude/RUNBOOK.md`
- 빈 섹션을 미리 만들어두지 않는다. 실제로 채울 내용이 생겼을 때 그 순간에 섹션(또는 새 파일)을 추가한다.
