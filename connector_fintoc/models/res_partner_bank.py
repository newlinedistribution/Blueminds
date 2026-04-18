# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError
from fintoc import Fintoc
import logging
_logger = logging.getLogger(__name__)


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    fintoc_id = fields.Char('Fintoc Id')
    fintoc_token = fields.Char('Fintoc Token', company_dependent=True)
    fintoc_days = fields.Integer('Days Lookup')

    def update_id(self):
        fintoc_api_key = self.company_id.fintoc_api_key or self.env.company.fintoc_api_key
        
        if not fintoc_api_key:
            raise UserError("Falta configurar 'Fintoc Api Key' en los Ajustes de la Compañía (Ajustes -> Compañías -> Seleccionar compañía).")
        if not self.fintoc_token:
            raise UserError("Falta configurar el 'Fintoc Token' en esta Cuenta Bancaria.")
            
        try:
            client = Fintoc(fintoc_api_key)
        except Exception as e:
            raise UserError("Invalid API Key %s (%s)" % (fintoc_api_key, e))
        try:
            link = client.links.get(self.fintoc_token)
        except Exception as e:
            raise UserError("Invalid API Token %s (%s)" % (self.fintoc_token, e))
        try:
            accounts = link.accounts.all()
            fintoc_id = None
            for account in accounts:
                if account.number == self.acc_number:
                    fintoc_id = account.id
                    break
            if fintoc_id is None:
                raise UserError("Invalid Account Number %s" % self.acc_number)
            self.fintoc_id = fintoc_id
        except Exception as e:
            raise UserError(e)
