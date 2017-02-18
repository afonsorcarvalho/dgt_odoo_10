# -*- coding: utf-8 -*-
import time
from datetime import datetime,timedelta
from odoo import models, api, fields, models, SUPERUSER_ID, _
from odoo.addons import decimal_precision as dp
from odoo import netsvc
from odoo.exceptions import UserError

class DgtOsRequest(models.Model):
	_name = 'dgt_os.os.request'
	_inherit = ['mail.thread']
	_description = u'Solicitação de Serviço'
	_order = "id desc"

	@api.returns('self')
	def _default_stage(self):
		return self.env['maintenance.stage'].search([], limit=1)
	
	@api.multi
	def _track_subtype(self, init_values):
		self.ensure_one()
		if 'stage_id' in init_values and self.stage_id.sequence <= 1:
			return 'maintenance.mt_req_created'
		elif 'stage_id' in init_values and self.stage_id.sequence > 1:
			return 'maintenance.mt_req_status'
		return super(DgtOsRequest, self)._track_subtype(init_values)

	def _get_default_team_id(self):
		return self.env.ref('maintenance.equipment_team_maintenance', raise_if_not_found=False)


	name = fields.Char(
		'Solicitação Nº',default=lambda self: self.env['ir.sequence'].next_by_code('dgt_os.os.request'),
		copy=False, required=True,readonly=True)
	description = fields.Text('Descrição')
	request_date = fields.Date('Data da Solicitação', track_visibility='onchange', default=fields.Date.context_today)
	oss = fields.One2many(
		'dgt_os.os', 'request_id', 'Ordens de Serviço',
		copy=True, readonly=False, required=False) 
	owner_user_id = fields.Many2one('res.users', string='Criado por', default=lambda s: s.env.uid)
	cliente_id = fields.Many2one(
		'res.partner', 'Cliente',
		index=True, required=True,
		help='Escolha o cliente .')
	company_id = fields.Many2one(
		'res.company', 'Empresa',
		default=lambda self: self.env['res.company']._company_default_get('mrp.repair'))
	category_id = fields.Many2one('maintenance.equipment.category', related='equipments.category_id', string='Category', store=True, readonly=True)
	equipments = fields.Many2many('maintenance.equipment', string='Equipment', index=True)
	technician_user_id = fields.Many2one('res.users', string='Owner', track_visibility='onchange', oldname='user_id')
	stage_id = fields.Many2one('maintenance.stage', string='Stage', track_visibility='onchange',
							   group_expand='_read_group_stage_ids', default=_default_stage)
	priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High')], string='Prioridade')
	color = fields.Integer('Color Index')
	close_date = fields.Date('Close Date')
	kanban_state = fields.Selection([('normal', 'In Progress'), ('blocked', 'Blocked'), ('done', 'Ready for next stage')],
									string='Kanban State', required=True, default='normal', track_visibility='onchange')
	# active = fields.Boolean(default=True, help="Set active to false to hide the maintenance request without deleting it.")
	archive = fields.Boolean(default=False, help="Set archive to true to hide the maintenance request without deleting it.")
	maintenance_type = fields.Selection([('corrective', 'Corretiva'), ('preventive', 'Preventiva'),('instalacao','Instalação'),('treinamento','Treinamento')], required=True, string='Maintenance Type', default="corrective")
	schedule_date = fields.Datetime('Scheduled Date')
	maintenance_team_id = fields.Many2one('maintenance.team', string='Team', required=True, default=_get_default_team_id)
	duration = fields.Float(help="Duration in minutes and seconds.")

	@api.multi
	def archive_equipment_request(self):
		self.write({'archive': True})

	@api.multi
	def reset_equipment_request(self):
		""" Reinsert the maintenance request into the maintenance pipe in the first stage"""
		first_stage_obj = self.env['maintenance.stage'].search([], order="sequence asc", limit=1)
		# self.write({'active': True, 'stage_id': first_stage_obj.id})
		self.write({'archive': False, 'stage_id': first_stage_obj.id})

	#@api.onchange('equipment_id')
	#def onchange_equipment_id(self):
	#	if self.equipment_id:
	#		self.technician_user_id = self.equipment_id.technician_user_id if self.equipment_id.technician_user_id else self.equipment_id.category_id.technician_user_id
	#		self.category_id = self.equipment_id.category_id
	#		if self.equipment_id.maintenance_team_id:
	#			self.maintenance_team_id = self.equipment_id.maintenance_team_id.id

	@api.onchange('category_id')
	def onchange_category_id(self):
		if not self.technician_user_id or not self.equipments or (self.technician_user_id and not self.equipments.technician_user_id):
			self.technician_user_id = self.category_id.technician_user_id
	
	@api.multi
	def action_gera_os(self):
		args = self.company_id and [('company_id', '=', self.company_id.id)] or []
		warehouse = self.env['stock.warehouse'].search(args, limit=1)
		equipments = self.equipments
		
		for line in equipments:
			vals = {
			#		#'name': self.name,
					'origin': self.name,
					'cliente_id': self.cliente_id.id,
					'date_planned': self.schedule_date,
					'date_scheduled': self.schedule_date,
					'date_execution': self.schedule_date,
					'maintenance_type': self.maintenance_type,
					'description':self.description,
					'equipment_id':line.id,
					'request_id':self.id,
					'priority':self.priority,
					'time_estimado':self.duration,
				
					}
			self.env['dgt_os.os'].create(vals)
		self.write({'stage_id': '2'})
		return True
	@api.model
	def create(self, vals):
		# context: no_log, because subtype already handle this
		self = self.with_context(mail_create_nolog=True)
		request = super(DgtOsRequest, self).create(vals)
		if request.owner_user_id:
			request.message_subscribe_users(user_ids=[request.owner_user_id.id])
		if request.equipments and not request.maintenance_team_id:
			request.maintenance_team_id = request.equipments.maintenance_team_id
		return request

	@api.multi
	def write(self, vals):
		# Overridden to reset the kanban_state to normal whenever
		# the stage (stage_id) of the Maintenance Request changes.
		if vals and 'kanban_state' not in vals and 'stage_id' in vals:
			vals['kanban_state'] = 'normal'
		if vals.get('owner_user_id'):
			self.message_subscribe_users(user_ids=[vals['owner_user_id']])
		res = super(DgtOsRequest, self).write(vals)
		if self.stage_id.done and 'stage_id' in vals:
			self.write({'close_date': fields.Date.today()})
		return res

	@api.model
	def _read_group_stage_ids(self, stages, domain, order):
		""" Read group customization in order to display all the stages in the
			kanban view, even if they are empty
		"""
		stage_ids = stages._search([], order=order, access_rights_uid=SUPERUSER_ID)
		return stages.browse(stage_ids)
