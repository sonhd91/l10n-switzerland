# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import api, fields, models

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    "out_invoice": "customer",
    "out_refund": "customer",
    "out_receipt": "customer",
    "in_invoice": "supplier",
    "in_refund": "supplier",
    "in_receipt": "supplier",
}


class PaymentRegister(models.TransientModel):
    """Backport from v13 of extend of account.payment.register"""

    _inherit = "account.payment.register"

    def _prepare_communication(self, invoices):
        """Return a single ISR reference

        to avoid duplicate of the same number when multiple payments are done
        on the same reference. As those payments are grouped by reference,
        we want a unique reference in communication.

        """
        # Only the first invoice needs to be tested as the grouping ensure
        # invoice with same ISR are in the same group.
        if invoices[0]._is_isr_supplier_invoice():
            return invoices[0].payment_reference or invoices[0].ref
        else:
            return " ".join(i.payment_reference or i.ref or i.name for i in invoices)

    def _get_payment_group_key(self, inv):
        """Define group key to group invoices in payments.
        In case of ISR reference number on the supplier invoice
        the group rule must separate the invoices by payment refs.

        As such reference is structured. This is required to export payments
        to bank in batch.
        """

        if inv._is_isr_supplier_invoice():

            ref = inv.payment_reference or inv.ref
            return (
                inv.commercial_partner_id,
                inv.currency_id,
                inv.partner_bank_id,
                ref,
            )
        else:
            return (
                inv.commercial_partner_id,
                inv.currency_id,
                inv.partner_bank_id,
                MAP_INVOICE_TYPE_PARTNER_TYPE[inv.move_type],
            )

    def get_payments_vals(self):
        """Compute the values for payments.

        :return: a list of payment values (dictionary).
        """
        grouped = defaultdict(lambda: self.env["account.move"])
        for inv in self.line_ids:
            if self.group_payment:
                grouped[self._get_payment_group_key(inv.move_id)] += inv.move_id
            else:
                # import pdb;pdb.set_trace()
                grouped[inv.move_id.id] += inv.move_id
        return [self._prepare_payment_vals(invoices) for invoices in grouped.values()]

    def _prepare_payment_vals(self, invoices):

        amount = self.env["account.payment"]._compute_payment_amount(
            invoices, invoices[0].currency_id, self.journal_id, self.payment_date
        )
        values = {
            "journal_id": self.journal_id.id,
            "payment_method_id": self.payment_method_id.id,
            "payment_date": self.payment_date,
            "communication": self._prepare_communication(invoices),
            "invoice_ids": [(6, 0, invoices.ids)],
            "payment_type": ("inbound" if amount > 0 else "outbound"),
            "amount": abs(amount),
            "currency_id": invoices[0].currency_id.id,
            "partner_id": invoices[0].commercial_partner_id.id,
            "partner_type": MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].move_type],
            "partner_bank_account_id": invoices[0].partner_bank_id.id,
        }
        return values


class AccountPayment(models.Model):

    _inherit = "account.payment"

    @api.model
    def _compute_payment_amount(self, invoices, currency, journal, date):
        """
        Compute the total amount for the payment wizard, get this from v13
        """
        company = journal.company_id
        currency = currency or journal.currency_id or company.currency_id
        date = date or fields.Date.today()

        if not invoices:
            return 0.0

        self.env["account.move"].flush(["move_type", "currency_id"])
        self.env["account.move.line"].flush(
            ["amount_residual", "amount_residual_currency", "move_id", "account_id"]
        )
        self.env["account.account"].flush(["user_type_id"])
        self.env["account.account.type"].flush(["type"])
        self._cr.execute(
            """
            SELECT
                move.move_type AS type,
                move.currency_id AS currency_id,
                SUM(line.amount_residual) AS amount_residual,
                SUM(line.amount_residual_currency) AS residual_currency
            FROM account_move move
            LEFT JOIN account_move_line line ON line.move_id = move.id
            LEFT JOIN account_account account ON account.id = line.account_id
            LEFT JOIN account_account_type account_type ON\
                account_type.id = account.user_type_id
            WHERE move.id IN %s
            AND account_type.type IN ('receivable', 'payable')
            GROUP BY move.id, move.move_type
        """,
            [tuple(invoices.ids)],
        )
        query_res = self._cr.dictfetchall()

        total = 0.0
        for res in query_res:
            move_currency = self.env["res.currency"].browse(res["currency_id"])
            if move_currency == currency and move_currency != company.currency_id:
                total += res["residual_currency"]
            else:
                total += company.currency_id._convert(
                    res["amount_residual"], currency, company, date
                )
        return total
