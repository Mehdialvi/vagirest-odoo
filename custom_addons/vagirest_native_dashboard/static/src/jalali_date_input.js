/** @odoo-module **/
import { Component, useState, onWillUpdateProps } from '@odoo/owl';
import { DateFromToValue } from '@spreadsheet/global_filters/components/filter_date_from_to_value/filter_date_from_to_value';
import { formatJalali, parseJalali } from './jalali_calendar';
const { DateTime } = luxon;

export class JalaliDateInput extends Component {
    static template = 'vagirest_native_dashboard.JalaliDateInput';
    static props = {
        value: { optional: true }, type: { type: String, optional: true },
        placeholder: { type: String, optional: true }, onChange: Function,
    };
    setup() {
        this.state = useState({ text: this.display(this.props.value), error: '' });
        onWillUpdateProps(props => {
            this.state.text = this.display(props.value);
            this.state.error = '';
        });
    }
    display(date) {
        return date ? formatJalali(date.year, date.month, date.day) : '';
    }
    onInput(event) {
        this.state.text = event.target.value;
        this.state.error = '';
    }
    commit(event) {
        const text = event.target.value.trim();
        if (!text) {
            this.state.error = '';
            this.props.onChange(undefined);
            return;
        }
        try {
            const [year, month, day] = parseJalali(text);
            const date = DateTime.local(year, month, day);
            if (!date.isValid) throw Error('تاریخ معتبر نیست.');
            this.state.error = '';
            this.state.text = formatJalali(year, month, day);
            this.props.onChange(date);
        } catch (error) {
            this.state.error = error.message;
        }
    }
}
// Replace only the spreadsheet from/to date inputs, retaining its native callbacks/domains.
DateFromToValue.components = { ...DateFromToValue.components, DateTimeInput: JalaliDateInput };
