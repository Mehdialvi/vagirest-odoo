import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    vagirest_phone_normalized = fields.Char(
        string="Normalized Phone",
        compute="_compute_vagirest_normalized_phones",
        store=True,
        index=True,
        copy=False,
    )

    vagirest_mobile_normalized = fields.Char(
        string="Normalized Mobile",
        compute="_compute_vagirest_normalized_phones",
        store=True,
        index=True,
        copy=False,
    )

    @staticmethod
    def _vagirest_normalize_phone(value):
        if not value:
            return False

        value = str(value).strip()

        translation = str.maketrans({
            "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
            "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
            "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
            "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        })

        value = value.translate(translation)
        digits = re.sub(r"\D", "", value)

        if not digits:
            return False

        # 0098xxxxxxxxxx -> 98xxxxxxxxxx
        if digits.startswith("0098"):
            digits = digits[2:]

        # 098xxxxxxxxxx -> 98xxxxxxxxxx
        elif digits.startswith("098") and len(digits) == 13:
            digits = digits[1:]

        # 0912... / 0313... -> 98912... / 98313...
        elif digits.startswith("0") and len(digits) == 11:
            digits = "98" + digits[1:]

        # 912... -> 98912...
        elif len(digits) == 10:
            digits = "98" + digits

        return digits

    @api.depends("phone", "mobile")
    def _compute_vagirest_normalized_phones(self):
        for partner in self:
            partner.vagirest_phone_normalized = (
                self._vagirest_normalize_phone(partner.phone)
            )
            partner.vagirest_mobile_normalized = (
                self._vagirest_normalize_phone(partner.mobile)
            )

    def _vagirest_find_phone_conflict(self, normalized, exclude_ids=None):
        if not normalized:
            return self.env["res.partner"]

        exclude_ids = exclude_ids or []

        domain = [
            ("id", "not in", exclude_ids),
            "|",
            ("vagirest_phone_normalized", "=", normalized),
            ("vagirest_mobile_normalized", "=", normalized),
        ]

        return (
            self.env["res.partner"]
            .with_context(active_test=False)
            .search(domain, limit=1)
        )

    def _vagirest_raise_duplicate(self, raw_number, conflict):
        raise ValidationError(
            _(
                "شماره تماس تکراری است.\n\n"
                'شماره "%(number)s" قبلاً برای مخاطب زیر ثبت شده است:\n'
                "%(contact)s\n"
                "شناسه مخاطب: %(id)s\n\n"
                "لطفاً مخاطب جدید ایجاد نکنید.\n"
                "اطلاعات ملاقات، کنگره، پیگیری یا فروش جدید را "
                "در Notes یا CRM همین مخاطب موجود ثبت کنید."
            )
            % {
                "number": raw_number,
                "contact": conflict.display_name,
                "id": conflict.id,
            }
        )

    @api.model_create_multi
    def create(self, vals_list):
        seen = {}

        for position, vals in enumerate(vals_list):
            current_record_numbers = set()

            for field_name in ("phone", "mobile"):
                raw_number = vals.get(field_name)
                normalized = self._vagirest_normalize_phone(raw_number)

                if not normalized:
                    continue

                # Same phone and mobile on the same contact is allowed.
                if normalized in current_record_numbers:
                    continue

                current_record_numbers.add(normalized)

                # Prevent duplicates inside batch imports.
                if normalized in seen and seen[normalized] != position:
                    raise ValidationError(
                        _(
                            'شماره "%(number)s" در بیش از یک مخاطب '
                            "در همین عملیات وارد شده است."
                        )
                        % {"number": raw_number}
                    )

                seen[normalized] = position

                conflict = self._vagirest_find_phone_conflict(normalized)

                if conflict:
                    self._vagirest_raise_duplicate(raw_number, conflict)

        return super().create(vals_list)

    def write(self, vals):
        # If phone/mobile is not changing, do not interfere with existing duplicates.
        if not {"phone", "mobile"}.intersection(vals):
            return super().write(vals)

        changed_numbers = {}

        for partner in self:
            checks = []

            if "phone" in vals:
                raw_phone = vals.get("phone")
                new_normalized = self._vagirest_normalize_phone(raw_phone)
                old_normalized = partner.vagirest_phone_normalized

                # Formatting-only changes remain allowed.
                if new_normalized and new_normalized != old_normalized:
                    checks.append((raw_phone, new_normalized))

            if "mobile" in vals:
                raw_mobile = vals.get("mobile")
                new_normalized = self._vagirest_normalize_phone(raw_mobile)
                old_normalized = partner.vagirest_mobile_normalized

                if new_normalized and new_normalized != old_normalized:
                    checks.append((raw_mobile, new_normalized))

            for raw_number, normalized in checks:
                previous_partner = changed_numbers.get(normalized)

                if previous_partner and previous_partner != partner.id:
                    raise ValidationError(
                        _(
                            'شماره "%(number)s" برای بیش از یک مخاطب '
                            "در همین عملیات انتخاب شده است."
                        )
                        % {"number": raw_number}
                    )

                changed_numbers[normalized] = partner.id

                conflict = self._vagirest_find_phone_conflict(
                    normalized,
                    exclude_ids=self.ids,
                )

                if conflict:
                    self._vagirest_raise_duplicate(raw_number, conflict)

        return super().write(vals)
