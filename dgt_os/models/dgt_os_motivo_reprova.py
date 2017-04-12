# -*- coding: utf-8 -*-

from odoo import api, fields, models


class dgtMotivoReprova(models.TransientModel):
	_name = 'dgt_os.os.motivo.reprova.transient'
	_description = u'Motivo da reprovação da Ordem de Serviço'

	motivo_reprova_id = fields.Many2one('dgt_os.os.motivo.reprova', u'Motivo da reprovação')

	@api.multi
	def action_motivo_reprova_apply(self):
		os = self.env['dgt_os.os'].browse(self.env.context.get('active_ids'))
		os.write({'motivo_reprova': self.motivo_reprova_id.id})
		return os.action_repair_reprovar()