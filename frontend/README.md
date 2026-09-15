# ssh136erp / frontend

매출 정산 화면 (Vue3 + Vite). 관리자 로그인 후:
- 상단: 오늘 실매출/매출액/순매출/건수
- 채널별 오늘 매출 요약
- 오늘 주문 목록 (클릭 시 품목/결제수단 상세)

## 실행

```bash
cp .env.example .env   # VITE_API_BASE_URL 을 backend 주소로 맞추기
npm install
npm run dev
```

## 배포 (cloudtype)

- 빌드 커맨드: `npm run build` → `dist/` 를 정적 호스팅
- 환경변수 `VITE_API_BASE_URL` 을 배포된 backend 도메인(`https://.../api`)으로 설정
- backend `.env` 의 `CORS_ALLOWED_ORIGINS` 에 이 frontend 배포 도메인을 추가해야 API 호출이 허용됩니다.

## 로그인 계정

Django 관리자 계정과 동일합니다 (`python manage.py createsuperuser` 로 만든 계정).
