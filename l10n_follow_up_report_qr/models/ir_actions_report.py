import io

from odoo import models
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        res = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids)
        report = self._get_report(report_ref)
        if (
            report.report_name in ("account_followup.report_followup_print_all")
            and report.model == "res.partner"
        ):
            partners = self.env[report.model].browse(res_ids)
            for partner in partners:
                invoices = partner.unreconciled_aml_ids.mapped("move_id")
                # Determine which invoices need a QR
                qr_inv_ids = []
                for invoice in invoices:
                    if invoice.company_id.country_code != "CH":
                        continue
                    if invoice.l10n_ch_is_qr_valid:
                        qr_inv_ids.append(invoice.id)
                streams_to_append = {}
                if qr_inv_ids:
                    qr_res = self._render_qweb_pdf_prepare_streams(
                        "l10n_ch.l10n_ch_qr_report", data, res_ids=qr_inv_ids
                    )
                    for invoice_id, stream in qr_res.items():
                        streams_to_append[invoice_id] = stream
                for _invoice_id, additional_stream in streams_to_append.items():
                    invoice_stream = res[partner.id]["stream"]
                    writer = OdooPdfFileWriter()
                    writer.appendPagesFromReader(
                        OdooPdfFileReader(invoice_stream, strict=False)
                    )
                    writer.appendPagesFromReader(
                        OdooPdfFileReader(additional_stream["stream"], strict=False)
                    )
                    new_pdf_stream = io.BytesIO()
                    writer.write(new_pdf_stream)
                    res[partner.id]["stream"] = new_pdf_stream
                    invoice_stream.close()
                    additional_stream["stream"].close()
        return res
