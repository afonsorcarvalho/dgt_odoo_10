# -*- coding: utf-8 -*-
# © 2016 Alessandro Fernandes Martini <alessandrofmartini@gmail.com>, Trustcode
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64

from lxml import objectify
from dateutil import parser
from random import SystemRandom

from odoo import api, models, fields
from odoo.exceptions import UserError


class WizardImportNfe(models.TransientModel):
    _name = 'wizard.import.nfe'

    nfe_xml = fields.Binary(u'XML da NFe')
    fiscal_position_id = fields.Many2one('account.fiscal.position',
                                         string='Posição Fiscal')
    payment_term_id = fields.Many2one('account.payment.term',
                                      string='Forma de Pagamento')
    invoice_id = fields.Many2one('account.invoice', string='Fatura')
    serie = fields.Many2one('invoice.eletronic', string="Série")

    @api.multi
    def action_import_nfe(self):
        if not self.nfe_xml:
            raise UserError('Por favor, insira um arquivo de NFe.')
        nfe_string = base64.b64decode(self.nfe_xml)
        nfe = objectify.fromstring(nfe_string)

        ide = nfe.NFe.infNFe.ide
        emit = nfe.NFe.infNFe.emit
        dest = nfe.NFe.infNFe.dest

        if hasattr(dest, 'CNPJ'):
            partner_doc = dest.CNPJ
        else:
            partner_doc = dest.CPF
        partner = self.env['res.partner'].search([
            ('cnpj_cpf', '=', partner_doc)])
        company = self.env['res.company'].search([
            ('cnpj_cpf', '=',  emit.CNPJ) ])

        entrada_saida = 'saida' if ide.tpNF == 1 else 'entrada'

        data_emissao = parser.parse(str(ide.dhEmi))
        data_fatura = parser.parse(str(ide.dhSaiEnt))

        numero_inv = self.env['invoice.eletronic'].search_count([])

        ambiente = 'homologacao' if ide.tpAmb == 2 else 'producao'

        num_controle = int(''.join([str(SystemRandom().randrange(9))
                           for i in range(8)]))

        invoice_eletronic = {
            'state': 'draft',
            'model': str(ide.mod),
            'tipo_operacao': entrada_saida,
            'invoice_id': self.invoice_id.id,
            'payment_term_id': self.payment_term_id.id,
            'partner_id': partner.id,
            'fiscal_position_id': self.fiscal_position_id.id,
            'code': 'AUTO ' + (self.invoice_id.number or ''),
            'data_emissao': data_emissao,
            'name': 'Documento Eletrônico: nº ' + str(numero_inv),
            'data_fatura': data_fatura,
            'company_id': company.id,
            'serie': self.serie.id,
            'ambiente': ambiente,
            'numero': numero_inv,
            'finalidade_emissao': str(ide.finNFe),
            'tipo_emissao': str(ide.tpEmis),
            'numero_controle': num_controle,
            'ind_final': str(ide.indFinal),
            'ind_pres': str(ide.indPres),
            'ind_dest': str(ide.idDest),
            'ind_ie_dest': str(dest.indIEDest),
        }
        self.env['invoice.eletronic'].create(invoice_eletronic)
