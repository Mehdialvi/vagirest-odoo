"""Pure matching checks, shared with the standalone test suite."""
from decimal import Decimal, ROUND_HALF_UP


def matching_error(*, amount, bank_amount, rounding, company_id, bank_company_id,
                   currency_id, bank_currency_id, partner_id, bank_partner_id,
                   posted, foreign_currency=False, evidence=False):
    if not posted:
        return 'گردش بانک هنوز ثبت قطعی نشده است.'
    if company_id != bank_company_id:
        return 'شرکت رسید و گردش بانک متفاوت است.'
    if currency_id != bank_currency_id or foreign_currency:
        return 'ارز رسید و گردش بانک باید یکسان باشد؛ تبدیل ارز خودکار انجام نمی‌شود.'
    if bank_partner_id and partner_id != bank_partner_id:
        return 'مشتری رسید و مشتری ثبت‌شده در گردش بانک متفاوت است.'
    if Decimal(str(bank_amount)) <= 0:
        return 'فقط گردش ورودی مثبت قابل تطبیق با رسید دریافت است.'
    # Quantise to the currency's actual rounding increment, including e.g. 0.05.
    step = Decimal(str(rounding))
    if step <= 0:
        return 'دقت واحد پول نامعتبر است.'
    a = (Decimal(str(amount))/step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    b = (Decimal(str(bank_amount))/step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    if a != b:
        return 'مبلغ رسید با گردش بانک برابر نیست؛ پرداخت تجمیعی یا کسر کارمزد نیازمند بررسی جداگانه است.'
    if not evidence:
        return 'تصویر رسید یا مرجع مستند پرداخت را ثبت کنید.'
    return False
