# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class MaintenanceRequest(models.Model):
	_inherit = 'maintenance.request'
	
	cliente_id = fields.Many2one(
		'res.partner', 'Cliente',
		index=True, required=True,
		help='Choose partner for whom the order will be invoiced and delivered.')
	maintenance_type = fields.Selection([('correctiva', 'Corretiva'), ('preventiva', 'Preventiva'),('instalacao', 'Instalação')], string='Maintenance Type', default="correctiva")
	
	
class MaintenanceEquipment(models.Model):
	_name = 'maintenance.equipment'	
	_inherit = ['mail.thread','maintenance.equipment']
	cliente_id = fields.Many2one(
		'res.partner', 'Cliente',
		index=True, required=True,
		help='Choose partner for whom the order will be invoiced and delivered.')	