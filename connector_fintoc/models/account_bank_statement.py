# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError
from datetime import date, datetime, timedelta
import logging
from fintoc import Fintoc



_logger = logging.getLogger(__name__)

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    fintoc_id = fields.Char(string='Fintoc Id')


    def onchange_document(self):
        fintoc_bank_id = self.env['res.partner.bank'].search([('fintoc_id','!=', False)])
        for fintoc_account in fintoc_bank_id:


            #Si tenemos Bank Statement Abierto lo usuamos
            BankStatement = self.env['account.bank.statement'].search([
                ('name','=',datetime.today().date()),
                ('is_complete','=', False),
                ('journal_id','=', fintoc_account.journal_id.id),], limit=1)

            if not BankStatement:
                balance_start = self.env['account.bank.statement.line'].search(
                domain=[
                    ('date', '<=', datetime.today().date()),
                    ('journal_id', '=', fintoc_account.journal_id.id),
                ],
                order='internal_index desc',
                limit=1
            ).running_balance or 0
                
                BankStatement = self.env['account.bank.statement'].create({
                    'name': datetime.today().date(),
                    'date': datetime.today().date(),
                    'balance_start':balance_start,})
                
            api_token = fintoc_account.fintoc_token
            api_key = fintoc_account.journal_id.company_id.fintoc_api_key
            if not api_key:
                raise UserError("La API Key de Fintoc no está configurada.")
            
            fintoc_days = 30
            if fintoc_account.fintoc_days>0:
                fintoc_days = fintoc_account.fintoc_days
                
            # Fintoc strict YYYY-MM-DD string format
            date_until_str = datetime.today().strftime('%Y-%m-%d')
            date_from_str = (datetime.today() - timedelta(days=fintoc_days)).strftime('%Y-%m-%d')
            
            values = {}
            try:
                client = Fintoc(api_key)
                link = client.links.get(api_token)
                
                account = None
                for acc in link.accounts.all():
                    if acc.number == fintoc_account.acc_number:
                        account = acc
                        break



                import requests
                
                try:
                    url = f"https://api.fintoc.com/v1/accounts/{account.id}/movements"
                    headers = {
                        "Authorization": api_key
                    }
                    params = {
                        "since": date_from_str,
                        "until": date_until_str,
                        "link_token": api_token
                    }
                    res = requests.get(url, headers=headers, params=params, timeout=10)
                    res.raise_for_status() # trigger except if HTTP error
                    movements_data = res.json()
                    
                    class SafeAttrDict:
                        def __init__(self, data):
                            self._data = data
                            
                        def __getattr__(self, name):
                            val = self._data.get(name)
                            if type(val) == dict:
                                return SafeAttrDict(val)
                            return val

                    movements = [SafeAttrDict(m) for m in movements_data]
                    
                except Exception as api_err:
                    _logger.warning("Fintoc API HTTP call failed: %s, falling back to unlimited fetch. Response text if any: %s", getattr(api_err, 'response', None), getattr(getattr(api_err, 'response', None), 'text', 'None'))
                    try:
                        params_unlimited = {"link_token": api_token}
                        res = requests.get(url, headers=headers, params=params_unlimited, timeout=10)
                        res.raise_for_status()
                        movements_data = res.json()
                        movements = [SafeAttrDict(m) for m in movements_data]
                    except Exception as fallback_err:
                        err_body = getattr(getattr(fallback_err, 'response', None), 'text', 'No Body')
                        raise UserError(f"Fintoc API HTTP Fallback Error: {fallback_err}\nDetalle Fintoc: {err_body}")
                        
                for movement in movements:
                    description = ""
                    sender = ""
                    rut = False
                    try:
                        fintoc_id = movement.id
                        amount = movement.amount  or "0"
                        if movement.currency == self.env.ref('base.EUR').name:
                            amount = amount / 100
                        elif movement.currency == self.env.ref('base.USD').name:
                            amount = amount / 100
                        description = movement.description or ""
                        try:
                            post_date = movement.post_date.date()
                        except:
                            post_date = movement.post_date[:10]
                        currency_id = movement.currency
                        movement_type = "transfer"
                        sender = ""
                        rut = False
                        if amount > 0:
                            if movement.sender_account and movement.sender_account.holder_name:
                                sender = movement.sender_account.holder_name
                                rut = movement.sender_account.holder_id
                        else:
                            if movement.recipient_account and movement.recipient_account.holder_name:
                                sender = movement.recipient_account.holder_name or ""
                                rut = movement.recipient_account.holder_id or False
                        values.update({
                            'date':post_date,
                            'ref': description,
                            'payment_ref':sender,
                            'partner': sender,
                            'fintoc_id': fintoc_id,
                            'amount': amount,
                            'currency_id' : currency_id,
                            'narration' : description,
                            'rut' : rut,
                            'journal_id' : fintoc_account.journal_id.id,
                            'statement_id':BankStatement,
                                        })
                        res = self._create_statement_lines(values)
                    except Exception as e:
                         _logger.warning('Error importing data')
                balance_end = BankStatement.balance_start + sum(BankStatement.line_ids.mapped('amount'))
                BankStatement.balance_end_real = balance_end or 0
            except Exception as e:
                _logger.info(str(e))
                raise UserError(str(e))

    def _create_statement_lines(self,val):
        account_bank_statement_line_obj = self.env['account.bank.statement.line']
        partner_id = self._find_partner(val.get('rut'),val.get('partner'))
        fintoc_id = self.env['account.bank.statement.line'].search([('fintoc_id','=',val.get('fintoc_id'))])
        if not fintoc_id:
            account_bank_statement_line_obj.create({
                    'fintoc_id': val.get('fintoc_id'),
                    'date': val.get('date'),
                    'ref': val.get('ref'),
                    'payment_ref': val.get('ref'),
                    'partner_id': partner_id,
                    'amount': val.get('amount'),
                    'currency_id': False,
                    'journal_id': val.get('journal_id'),
                    'statement_id': val.get('statement_id').id,
                    })
        return True


    def _find_partner(self,vat, partner):
        if vat == False:
            return False
        vat = vat.upper()
        if len(vat) == 9:
            # Format: XX.XXX.XXX-X
            formatted_vat = vat[0:8] + "-" + vat[8]
        elif len(vat) == 8:
            # Format: X.XXX.XXX-X
            formatted_vat = vat[0:7] + "-" + vat[7]
        partner_id = self.env['res.partner'].search([('vat','=',formatted_vat)], limit=1)
        if not partner_id:
            values = {
            "vat": formatted_vat,
            "name": partner or "",}
            partner_id = self.env["res.partner"].create(values)
        return partner_id.id

    def update_wo(self):
        self.onchange_document()
