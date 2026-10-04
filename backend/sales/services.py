"""
매출 취소(SaleCancel) 기록 공통 로직.
tosspos 웹훅 / matepos bulk-create / SaleSerializer 에서 공유한다.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Sale, SaleCancel

logger = logging.getLogger(__name__)


def _parse_cancelled_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, str) and value:
        dt = parse_datetime(value)
        if dt is not None:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
    return timezone.now()


def _parse_business_date(value: Any, fallback_dt: datetime | None = None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    if fallback_dt is not None:
        return fallback_dt.date()
    return None


def find_original_sale(
    *,
    source: str,
    store_code: str,
    channel_order_no: str | None = None,
    order_seq: str | None = None,
) -> Sale | None:
    """channel_order_no 우선, 없으면 order_seq 로 원주문 검색."""
    if channel_order_no:
        sale = (
            Sale.objects.filter(
                source=source,
                store_code=store_code,
                channel_order_no=channel_order_no,
            )
            .order_by("-business_date", "-id")
            .first()
        )
        if sale:
            return sale
    if order_seq:
        return (
            Sale.objects.filter(
                source=source,
                store_code=store_code,
                order_seq=str(order_seq),
            )
            .order_by("-business_date", "-id")
            .first()
        )
    return None


@transaction.atomic
def record_sale_cancel(
    *,
    source: str,
    store_code: str,
    channel_order_no: str | None = None,
    order_seq: str | None = None,
    cancelled_at: Any = None,
    cancel_reason: str = "",
    cancel_amount: int | None = None,
    business_date: Any = None,
    raw_data: dict | None = None,
    sale: Sale | None = None,
) -> SaleCancel:
    """
    취소 이벤트 저장.
    - 원 Sale 찾으면 payment_status=결제취소 + FK 연결
    - 못 찾으면 sale=null, process_note 에 미매칭 메시지
    - 유니크 충돌 시 기존 행 process_note 갱신 후 반환 (예외 미전파)
    """
    channel_order_no = (channel_order_no or "").strip()
    cancelled_dt = _parse_cancelled_at(cancelled_at)
    biz_date = _parse_business_date(business_date, cancelled_dt)
    process_note = ""

    if sale is None:
        sale = find_original_sale(
            source=source,
            store_code=store_code,
            channel_order_no=channel_order_no or None,
            order_seq=order_seq,
        )

    if sale is not None:
        if sale.payment_status != Sale.PaymentStatus.CANCELLED:
            sale.payment_status = Sale.PaymentStatus.CANCELLED
            sale.save(update_fields=["payment_status", "updated_at"])
        if cancel_amount is None:
            cancel_amount = int(sale.actual_sale_amount or 0)
        if not channel_order_no and sale.channel_order_no:
            channel_order_no = sale.channel_order_no
        if biz_date is None and sale.business_date:
            biz_date = sale.business_date
    else:
        process_note = (
            f"원주문 미매칭: source={source} store={store_code} "
            f"channel_order_no={channel_order_no or '-'} order_seq={order_seq or '-'}"
        )
        if cancel_amount is None:
            cancel_amount = 0
        logger.warning("SaleCancel 원주문 미매칭: %s", process_note)

    try:
        cancel = SaleCancel.objects.create(
            sale=sale,
            source=source,
            store_code=store_code,
            channel_order_no=channel_order_no,
            cancelled_at=cancelled_dt,
            cancel_reason=cancel_reason or "",
            cancel_amount=int(cancel_amount or 0),
            business_date=biz_date,
            process_note=process_note,
            is_read=False,
            raw_data=raw_data,
        )
        return cancel
    except IntegrityError:
        existing = (
            SaleCancel.objects.filter(
                source=source,
                store_code=store_code,
                channel_order_no=channel_order_no,
                cancelled_at=cancelled_dt,
            )
            .order_by("-id")
            .first()
        )
        conflict_msg = (
            f"유니크 충돌: 동일 취소 재수신 "
            f"({source}/{store_code}/{channel_order_no}/{cancelled_dt.isoformat()})"
        )
        if existing is None:
            logger.error("SaleCancel IntegrityError but no existing row: %s", conflict_msg)
            raise
        notes = [n for n in (existing.process_note, conflict_msg) if n]
        existing.process_note = "\n".join(notes)
        existing.is_read = False
        if sale is not None and existing.sale_id is None:
            existing.sale = sale
        if cancel_reason and not existing.cancel_reason:
            existing.cancel_reason = cancel_reason
        existing.save(
            update_fields=["process_note", "is_read", "sale", "cancel_reason", "updated_at"]
        )
        logger.info("SaleCancel 유니크 충돌 처리: id=%s %s", existing.id, conflict_msg)
        return existing
