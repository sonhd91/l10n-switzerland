# Copyright 2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64

from odoo import _, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def generate_email(self, res_ids, fields=None):
        # Method overridden in order remove QR/ISR payslips and use
        # Invoice report with payslip generated by this module
        # https://github.com/odoo/odoo/blob/13.0/addons/l10n_ch/models/mail_template.py#L12

        result = super().generate_email(res_ids, fields)
        if self._should_print_invoice_attachment():
            for invoice in self.env[self.model_id.model].browse(res_ids):
                invoice_attachments = self.generate_invoice_attachment(invoice)
                result[invoice.id]["attachments"] = invoice_attachments
        return result

    def _should_print_invoice_attachment(self):
        # report name is not mandatory and odoo implementation does not rely on it
        # but in this case we assume that this is report linked to the template
        if (
            self.model_id.model == "account.move"
            and self.report_template.report_name
            == "l10n_ch_invoice_reports.account_move_payment_report"
        ):
            return True

    def generate_invoice_attachment(self, invoice):
        # force translation of attachment's name according to partner's lang
        self = self.with_context(lang=invoice.partner_id.lang)
        report_name = _("invoice_%s_with_payslip.pdf") % invoice.name.replace("/", "_")
        report_pdf = self.report_template._render_qweb_pdf([invoice.id])[0]
        report_pdf = base64.b64encode(report_pdf)
        return [(report_name, report_pdf)]