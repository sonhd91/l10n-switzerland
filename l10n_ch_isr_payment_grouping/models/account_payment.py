# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


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
