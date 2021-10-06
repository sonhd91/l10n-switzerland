from odoo import api, models

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

    @api.model
    def _get_batch_communication(self, batch):
        """Helper to compute the communication based on the batch.
        :param batch_result:    A batch returned by '_get_batches'.
        :return:                A string representing a communication to be set on payment.
        """
        lines = batch.get("lines")
        if batch["key_values"].get("payment_reference"):
            return batch["key_values"].get("payment_reference") or lines.move_id[0].ref
        else:
            for line in lines:
                if not line.name:
                    line.name = line.move_id.name
            return super(PaymentRegister, self)._get_batch_communication(batch)

    def _get_line_batch_key(self, inv):
        if inv.move_id._is_isr_supplier_invoice():

            ref = inv.move_id.payment_reference or inv.ref
            return {
                "partner_id": inv.partner_id.id,
                "account_id": inv.account_id.id,
                "currency_id": (inv.currency_id or inv.company_currency_id).id,
                "partner_bank_id": inv.move_id.partner_bank_id.id,
                "partner_type": "customer"
                if inv.account_internal_type == "receivable"
                else "supplier",
                "payment_type": "inbound" if inv.balance > 0.0 else "outbound",
                "payment_reference": ref,
            }
        else:
            return super()._get_line_batch_key(inv)

    def get_payments_vals(self):
        """Compute the values for payments.

        :return: a list of payment values (dictionary).
        """
        batch_result = self._get_batches()

        res = []
        for batch in batch_result:
            if not self.group_payment:
                lines = batch.get("lines")
                for line in lines:
                    batch["lines"] = line
                    res.append(self._prepare_payment_vals(batch))

            else:
                res.append(self._prepare_payment_vals(batch))
        return res

    def _prepare_payment_vals(self, batch):
        lines = batch.get("lines")
        amount = self.env["account.payment"]._compute_payment_amount(
            lines.move_id,
            lines[0].move_id.currency_id,
            self.journal_id,
            self.payment_date,
        )

        values = {
            "journal_id": self.journal_id.id,
            "payment_method_id": self.payment_method_id.id,
            "payment_date": self.payment_date,
            "communication": self._get_batch_communication(batch),
            "invoice_ids": [(6, 0, lines.move_id.ids)],
            "payment_type": ("inbound" if amount > 0 else "outbound"),
            "amount": abs(amount),
            "currency_id": lines.currency_id.id,
            "partner_id": lines.partner_id.id,
        }
        return values
