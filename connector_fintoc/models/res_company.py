# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    fintoc_api_key = fields.Char('Fintoc Api Key', company_dependent=True)