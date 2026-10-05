/** @odoo-module **/
// Calendar conversion uses the browser's Persian calendar; stored Odoo dates stay Gregorian.
const calendar = new Intl.DateTimeFormat('en-US-u-ca-persian-nu-latn', {
    timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit',
});
export function toJalali(year, month, day) {
    const parts = calendar.formatToParts(new Date(Date.UTC(year, month - 1, day, 12)));
    const value = Object.fromEntries(parts.filter(p => ['year', 'month', 'day'].includes(p.type)).map(p => [p.type, Number(p.value)]));
    return [value.year, value.month, value.day];
}
export function formatJalali(year, month, day) {
    return toJalali(year, month, day).map((n, i) => String(n).padStart(i ? 2 : 4, '0')).join('/');
}
export function parseJalali(text) {
    const digits = '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩';
    const normalized = text.trim().replace(/[۰-۹٠-٩]/g, c => String(digits.indexOf(c) % 10));
    const match = /^(\d{4})[\/.-](\d{1,2})[\/.-](\d{1,2})$/.exec(normalized);
    if (!match) throw Error('تاریخ را به شکل ۱۴۰۵/۰۷/۰۱ وارد کنید.');
    const [year, month, day] = match.slice(1).map(Number);
    if (year < 1200 || year > 1600 || month < 1 || month > 12 || day < 1 || day > 31) throw Error('تاریخ شمسی معتبر نیست.');
    const wanted = year * 10000 + month * 100 + day;
    const milliseconds = 86400000;
    let low = Math.floor(Date.UTC(year + 620, 0, 1) / milliseconds);
    let high = Math.floor(Date.UTC(year + 623, 0, 1) / milliseconds);
    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const date = new Date(mid * milliseconds);
        const [jy, jm, jd] = toJalali(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
        const candidate = jy * 10000 + jm * 100 + jd;
        if (candidate === wanted) return [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()];
        if (candidate < wanted) low = mid + 1; else high = mid - 1;
    }
    throw Error('این روز در تقویم شمسی وجود ندارد.');
}
