# -*- coding: utf-8 -*-
import time
from datetime import datetime,timedelta
from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo import netsvc
from odoo.exceptions import UserError


class DgtOs(models.Model):
	_name = 'dgt_os.os'
	_description = 'Ordem de Servico'
	_inherit = ['mail.thread','ir.needaction_mixin']
	_order = 'name'
	
	STATE_SELECTION = [
		('draft', 'Rascunho'),
		('orcamento', 'Em Orçamento'),
		('orcada', 'Orçada'),
		('aprovacao', 'Esperando Aprovação'),
		('released', 'Esperando peças'),
		('cancel', 'Cancelada'),
		('confirmed', 'Autorizada'),
		('ready', 'Pronto para Execução'),
		('under_repair', 'Em execução'),
		('2binvoiced', 'à Faturar'),
		('invoice_except', 'Exceção de Faturamento'),
		('done', 'Concluído'),
		('reprovado', 'Reprovado')]
	

	MAINTENANCE_TYPE_SELECTION = [
		('corrective', 'Corretiva'),
		('preventive', 'Preventiva'),
		('instalacao','Instalação'),
		('treinamento','Treinamento')]
	
	@api.multi
	def _track_subtype(self, init_values):
		self.ensure_one()
		if 'state' in init_values and self.state == 'ready':
			return 'mro.mt_order_confirmed'
		return super(DgtOs, self)._track_subtype(init_values)
	
	def _get_available_parts(self):
		for order in self:
			line_ids = []
			available_line_ids = []
			done_line_ids = []
			if order.procurement_group_id:
				for procurement in order.procurement_group_id.procurement_ids:
					line_ids += [move.id for move in procurement.move_ids if move.location_dest_id.id == order.location_id.id]
					available_line_ids += [move.id for move in procurement.move_ids if move.location_dest_id.id == order.location_id.id and move.state == 'assigned']
					done_line_ids += [move.id for move in procurement.move_ids if move.location_dest_id.id == order.location_id.id and move.state == 'done']
			order.pecas_ready_lines = line_ids
			order.pecas_move_lines = available_line_ids
			order.pecas_moved_lines = done_line_ids
				
	@api.model
	def _gera_qr(self):
		self.qr = self.name + "\n" + self.cliente_id.name + "\n" + self.equipment_id.name + "-" + self.equipment_id.serial_no
		
	@api.model
	def _default_stock_location(self):
		warehouse = self.env.ref('stock.warehouse0', raise_if_not_found=False)
		if warehouse:
			return warehouse.lot_stock_id.id
		return False
	
	@api.model
	def _default_journal(self):
		if self._context.get('default_journal_id', False):
			return self.env['account.journal'].browse(self._context.get('default_journal_id'))
		inv_type = self._context.get('type', 'out_invoice')
		inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
		company_id = self._context.get('company_id', self.env.user.company_id.id)
		domain = [
			('company_id', '=', company_id),
		]
		return self.env['account.journal'].search(domain, limit=1)
	@api.model
	def _default_currency(self):
		journal = self._default_journal()
		return journal.currency_id or journal.company_id.currency_id
		
	name = fields.Char(
		'O.S. Nº',default=lambda self: self.env['ir.sequence'].next_by_code('dgt_os.os'),
		copy=False, required=True,readonly=True)
	origin = fields.Char('Source Document', size=64, readonly=True, states={'draft': [('readonly', False)]},
		help="Referencia ao documento que gerou a ordem de servico.")
	state = fields.Selection(STATE_SELECTION, string='Status',
		copy=False, default='draft', readonly=True, track_visibility='onchange',
		help="* The \'Draft\' status is used when a user is encoding a new and unconfirmed repair order.\n"
			"* The \'Confirmed\' status is used when a user confirms the repair order.\n"
			"* The \'Ready to Repair\' status is used to start to repairing, user can start repairing only after repair order is confirmed.\n"
			"* The \'To be Invoiced\' status is used to generate the invoice before or after repairing done.\n"
			"* The \'Done\' status is set when repairing is completed.\n" 
			"* The \'Cancelled\' status is used when user cancel repair order.")
	kanban_state = fields.Selection([('normal', 'In Progress'), ('blocked', 'Blocked'), ('done', 'Ready for next stage')],
									string='Kanban State', required=True, default='normal', track_visibility='onchange')
	priority = fields.Selection([('0','Normal'),('1',"Baixa"),('2',"Alta"),('3','Muito Alta')],'Prioridade',default=0)
	color = fields.Integer('Color Index')
	maintenance_type = fields.Selection(MAINTENANCE_TYPE_SELECTION, string='Tipo de Manutenção',required=True, default="corrective")
	time_execution = fields.Float("Tempo Execução", compute='_compute_time_execution', help="Tempo de execução em minutos",store=True)
	time_estimado = fields.Integer("Tempo Estimado",help="Tempo estimado de execução em minutos",store=True)
	task_id = fields.Many2one('dgt_os.os.task', 'Task', readonly=True, states={'draft': [('readonly', False)]})
	date_planned = fields.Datetime('Planned Date', required=True,  readonly=True, default=time.strftime('%Y-%m-%d %H:%M:%S'))
	date_scheduled = fields.Datetime('Scheduled Date', required=True,  readonly=True, default=time.strftime('%Y-%m-%d %H:%M:%S'))
	date_execution = fields.Datetime('Execution Date', required=True,  default=time.strftime('%Y-%m-%d %H:%M:%S'))
	currency_id = fields.Many2one('res.currency', string='Currency',
		required=True, readonly=True,
		default=_default_currency, track_visibility='always')
	request_id = fields.Many2one(
		'dgt_os.os.request', 'Solicitação Ref.',
		index=True, ondelete='restrict')
	tools_description = fields.Text('Descrição das Ferramentas',translate=True)
	labor_description = fields.Text('Descrição dos Ensaios',translate=True)
	operations_description = fields.Text('Descrição das Operações',translate=True)
	documentation_description = fields.Text('Descrição da Documentação',translate=True)
	problem_description = fields.Text('Descrição do Defeito')
	#currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
	#currency_id = pricelist_id.currency_id
	
	partner_invoice_id = fields.Many2one('res.partner', 'Fatura para')
	cliente_id = fields.Many2one(
		'res.partner', 'Cliente',
		index=True, required=True,
		help='Escolha o cliente que sera para fatura.')
	address_id = fields.Many2one(
		'res.partner', 'Delivery Address',
		domain="[('parent_id','=',cliente_id)]",
		)
	default_address_id = fields.Many2one('res.partner',
		compute='_compute_default_address_id'
		)
	
	location_id = fields.Many2one(
		'stock.location', 'Current Location',
		default=_default_stock_location,
		index=True,  required=False,
		)
	location_dest_id = fields.Many2one(
		'stock.location', 'Delivery Location',
		 required=False,
		)
	lot_id = fields.Many2one(
		'stock.production.lot', 'Repaired Lot',
		domain="[('product_id','=', product_id)]",
		help="Products repaired are all belonging to this lot", oldname="prodlot_id")
	guarantee_limit = fields.Date('Warranty Expiration')
	pecas = fields.One2many(
		'dgt_os.os.pecas.line', 'os_id', 'Pecas',
		copy=True)
		
	pecas_ready_lines = fields.One2many('stock.move', compute='_get_available_parts')
	pecas_move_lines = fields.One2many('stock.move', compute='_get_available_parts')
	pecas_moved_lines = fields.One2many('stock.move', compute='_get_available_parts')
	servicos = fields.One2many(
		'dgt_os.os.servicos.line', 'os_id', u'Serviços',
		copy=True, readonly=False)
	relatorios = fields.One2many(
		'dgt_os.os.relatorio.servico', 'os_id', u'Relatórios',
		copy=True, readonly=False)
	pricelist_id = fields.Many2one(
		'product.pricelist', 'Lista de preço',
		default=lambda self: self.env['product.pricelist'].search([], limit=1).id,
		help='Lista de preco para o cliente selecionado.')
	invoice_method = fields.Selection([
		("none", "Não Faturar"),
		("b4repair", "Antes do Serviço"),
		("after_repair", "Depois do Serviço")], string="Faturamento",
		default='none', index=True, required=True,
		help='Selecione \'Antes do Servico\' or \'Depois do Servico\' caso queira faturar antes ou depois de realizado o servico. \'Nao Faturar\' nao gera fatura.')
	invoice_id = fields.Many2one(
		'account.invoice', 'Fatura peças',
		copy=False,  track_visibility="onchange")
	invoice_servico_id = fields.Many2one(
		'account.invoice', 'Fatura Serviço',
		copy=False,  track_visibility="onchange")
	internal_notes = fields.Text('Notas internas')
	quotation_notes = fields.Text('Notas de Orçamento')
	company_id = fields.Many2one(
		'res.company', 'Empresa',
		default=lambda self: self.env['res.company']._company_default_get('mrp.repair'))
	tecnicos_id = fields.Many2many(
		'hr.employee',string = 'Técnicos',compute='_compute_tecnicos_id',store=True
		)
	invoiced = fields.Boolean('Faturado', copy=False, readonly=True)
	repaired = fields.Boolean(u'Concluído', copy=False, readonly=True)
	amount_untaxed = fields.Float('Untaxed Amount', compute='_amount_untaxed', store=True)
	amount_tax = fields.Float('Impostos', compute='_amount_tax', store=True)
	amount_total = fields.Float('Total', compute='_amount_total', store=True)
	amount_untaxed_pecas = fields.Float('Total Peças s/ impostos',compute='_amount_untaxed',  store=True)
	amount_tax_pecas = fields.Float('Impostos Peças', compute='_amount_tax', store=True)
	amount_total_pecas = fields.Float('Total Peças',compute='_amount_total',  store=True)
	amount_total_pecas_no_inv = fields.Float('Total Peças Não Faturada',compute='_amount_total',  store=True)
	amount_untaxed_servicos = fields.Float('Total Serviços s/ impostos',compute='_amount_untaxed',  store=True)
	amount_tax_servicos = fields.Float('Impostos Serviços', compute='_amount_tax', store=True)
	amount_total_servicos = fields.Float('Total Serviços',compute='_amount_total',  store=True)
	equipment_id = fields.Many2one(
		'maintenance.equipment', 'Equipamento', 
		index=True, required=True,
		help='Escolha o equipamento referente a Ordem de Servico.'
		)
	description = fields.Text()
	procurement_group_id = fields.Many2one('procurement.group', 'Procurement group', copy=False)
	qr = fields.Text('Qr code',compute='_gera_qr',readonly=True)
	motivo_reprova = fields.Many2one('dgt_os.os.motivo.reprova', string='Motivo', index=True, track_visibility='onchange')
	account_analytic_id = fields.Many2one('account.analytic.account', string="Conta analítica")
	#category_id = fields.Many2many(related='equipment_id.category_id', string='Categoria do Equipamento', readonly=True)
	
	@api.multi
	@api.onchange('relatorios')
	def onchange_relatorios(self):
		if self.relatorios:
			# tempo = 0.0
			# for rel in self.relatorios:
				# tempo += rel.time_execution
			# self.time_execution = tempo
			self._compute_tecnicos_id()
			
	
	
	@api.multi
	@api.depends('relatorios')
	def _compute_time_execution(self):
		#for os in self:
			if self.relatorios:
				tempo = 0.0
				for rel in self.relatorios:
					tempo += rel.time_execution
				self.update({'time_execution' : tempo})
				#self._compute_tecnicos_id()
	
	@api.onchange('equipment_id')
	def onchange_equipment_id(self):
		if self.equipment_id:
			self.cliente_id = self.equipment_id.cliente_id
			self.category_id = self.equipment_id.category_id
			
	@api.onchange('date_planned')
	def onchange_planned_date(self):
		self.date_scheduled = self.date_planned

	@api.onchange('date_scheduled')
	def onchange_scheduled_date(self):
		self.date_execution = self.date_scheduled

	@api.onchange('date_execution')
	def onchange_execution_date(self):
		if self.state == 'draft':
			self.date_planned = self.date_execution
		else:
			self.date_scheduled = self.date_execution
			
	@api.onchange('task_id')
	def onchange_task(self):
		task = self.task_id
		new_pecas_lines = []
		for line in task.pecas_lines:
			new_pecas_lines.append([0,0,{
				'name': line.name,
				'pecas_id': line.pecas_id.id,
				'pecas_qty': line.pecas_qty,
				'pecas_uom': line.pecas_uom.id,
				}])
		self.pecas_lines = new_pecas_lines
		self.description = task.name
		self.tools_description = task.tools_description
		self.labor_description = task.labor_description
		self.operations_description = task.operations_description
		self.documentation_description = task.documentation_description
	
	@api.multi
	@api.depends('relatorios')
	def _compute_tecnicos_id(self):
		tecnicos = self.env['hr.employee']
		if self.relatorios:
			for rel in self.relatorios:
				if rel.tecnicos_id:
					for tec in rel.tecnicos_id:
						tecnicos |= tec
		self.tecnicos_id = tecnicos
	
	@api.one
	@api.depends('cliente_id')
	def _compute_default_address_id(self):
		if self.cliente_id:
			self.default_address_id = self.cliente_id.address_get(['contact'])['contact']
			
	#*********************************
	#CALCULANDO TOTAL SEM TAXAS
	#*********************************
	@api.one
	@api.depends('pecas.price_subtotal', 
			'servicos.price_subtotal', 
			'pricelist_id.currency_id')
	def _amount_untaxed(self):
		total_pecas = sum(p.price_subtotal for p in self.pecas)
		total_servicos = sum(s.price_subtotal for s in self.servicos)
		total = total_pecas + total_servicos
		self.amount_untaxed_pecas = self.pricelist_id.currency_id.round(total_pecas)
		self.amount_untaxed_servicos = self.pricelist_id.currency_id.round(total_servicos)
		self.amount_untaxed = self.pricelist_id.currency_id.round(total)
	
	#*********************************
	#CALCULANDO TOTAL COM TAXAS
	#*********************************
	@api.one
	@api.depends('pecas.price_unit', 'pecas.product_uom_qty', 'pecas.product_id',
				'servicos.price_unit', 'servicos.product_uom_qty', 'servicos.product_id',
				'pricelist_id.currency_id', 'cliente_id')
	def _amount_tax(self):
		val_pecas = 0.0
		val_servicos = 0.0
		for p in self.pecas:
			if p.to_invoice and p.tax_id:
				tax_calculate_pecas = p.tax_id.compute_all(p.price_unit, self.pricelist_id.currency_id, p.product_uom_qty, p.product_id, self.cliente_id)
				for c in tax_calculate_pecas['taxes']:
					val_pecas += c['amount']
		for s in self.servicos:
			if s.to_invoice and s.tax_id:
				tax_calculate_servicos = s.tax_id.compute_all(s.price_unit, self.pricelist_id.currency_id, s.product_uom_qty, s.product_id, self.cliente_id)
				for c in tax_calculate_servicos['taxes']:
					val_servicos += c['amount']
		self.amount_tax_pecas = val_pecas
		self.amount_tax_servicos = val_servicos
		self.amount_tax = val_pecas + val_servicos
	
	@api.one
	@api.depends('amount_untaxed', 'amount_tax')
	def _amount_total(self):
		self.amount_total_servicos = self.pricelist_id.currency_id.round(self.amount_untaxed_servicos + self.amount_tax_servicos)
		total_pecas_no_inv = sum(p.price_subtotal_no_invoiced for p in self.pecas)
		self.amount_total_pecas_no_inv = self.pricelist_id.currency_id.round(total_pecas_no_inv)
		self.amount_total_pecas = self.pricelist_id.currency_id.round(self.amount_untaxed_pecas + self.amount_tax_pecas)
		self.amount_total = self.pricelist_id.currency_id.round(self.amount_untaxed + self.amount_tax)
	_sql_constraints = [('name', 'unique (name)', 'The name of the Repair Order must be unique!'),]
	
	@api.onchange('cliente_id')
	def onchange_cliente_id(self):
		if self.cliente_id:
			#self.partner_id = self.cliente_id
			self.partner_invoice_id = self.cliente_id.id
			
	@api.onchange('pecas')
	def onchange_pecas(self):
		self.location_dest_id = self.location_id.id
	
	#@api.onchange('relatorios')
	#def onchange_relatorios(self):
	#	soma = 0
	#	for rel in self.relatorios:
	#		for at in rel.atendimentos:
	#			soma = soma + at.tempo
	#	self.time_execution = soma/60
		
	@api.onchange('location_id')
	def onchange_location_id(self):
		self.location_dest_id = self.location_id.id
	
	@api.onchange('cliente_id')
	def onchange_cliente_id(self):
		if not self.cliente_id:
			self.address_id = False
			self.partner_invoice_id = False
			self.pricelist_id = self.env['product.pricelist'].search([], limit=1).id
		else:
			addresses = self.cliente_id.address_get(['delivery', 'invoice', 'contact'])
			self.address_id = addresses['delivery'] or addresses['contact']
			self.partner_invoice_id = addresses['invoice']
			self.pricelist_id = self.cliente_id.property_product_pricelist.id
			
		
	@api.multi
	def action_repair_cancel_draft(self):
		if self.filtered(lambda dgt_os: dgt_os.state != 'cancel'):
			raise UserError(_("Repair must be canceled in order to reset it to draft."))
		self.mapped('pecas').write({'state': 'draft'})
		return self.write({'state': 'draft'})
	
	@api.multi
	def action_repair_confirm(self):
		""" Repair order state is set to 'To be invoiced' when invoice method
		is 'Before repair' else state becomes 'Confirmed'.
		@param *arg: Arguments
		@return: True
		"""
		if self.filtered(lambda dgt_os: dgt_os.state != 'draft'):
			raise UserError(_("Can only confirm draft repairs."))
		
		procurement_obj = self.env['procurement.order']
		for order in self:
			proc_ids = []
			group_id = self.env['procurement.group'].create({'name': order.name})
			for line in order.pecas:
				vals = {
					'name': order.name,
					'origin': order.name,
					'company_id': order.company_id.id,
					'group_id': group_id.id,
					'date_planned': order.date_planned,
					'product_id': line.product_id.id,
					'product_qty': line.product_uom_qty,
					'product_uom': line.product_uom.id,
					'location_id': line.location_id.id,
					'location_dest_id': line.location_dest_id.id
					}
				proc_id = procurement_obj.create(vals)
				proc_ids.append(proc_id)
			procurement_obj.run(proc_ids)
			order.write({'state':'orcamento','procurement_group_id':group_id.id})
		
		
		#before_repair = self.filtered(lambda dgt_os: dgt_os.invoice_method == 'b4repair')
		#before_repair.write({'state': '2binvoiced'})
		#to_confirm = self - before_repair
		#to_confirm_operations = to_confirm.mapped('pecas')
		#for operation in to_confirm_operations:
		#	if operation.product_id.tracking != 'none' and not operation.lot_id:
		#		raise UserError(_("Serial number is required for operation line with product '%s'") % (operation.product_id.name))
		#to_confirm_operations.write({'state': 'confirmed'})
		#to_confirm.write({'state': 'confirmed'})
		return True
	
	@api.multi
	def action_repair_orcado(self):
		if self.filtered(lambda dgt_os: dgt_os.state == 'done'):
			raise UserError(_("O.S já concluída."))
		if self.filtered(lambda dgt_os: dgt_os.state == 'orcada'):
			raise UserError(_('O.S. já orçada.'))
		return self.write({'state': 'orcada'})
		
	@api.multi
	def action_repair_autorizar(self):
		
		if self.filtered(lambda dgt_os: dgt_os.state == 'done'):
			raise UserError(_("O.S já concluída."))
		if self.filtered(lambda dgt_os: dgt_os.state == 'confirmed'):
			raise UserError(_('O.S. já autorizada.'))
		if self.filtered(lambda dgt_os: dgt_os.invoice_method == 'b4repair'):
			return self.write({'state': '2binvoiced'})
		return self.write({'state': 'confirmed'})
	
	@api.multi
	def action_repair_executar(self):
		if self.filtered(lambda dgt_os: dgt_os.state == 'done'):
			raise UserError(_("O.S já concluída."))
		if self.filtered(lambda dgt_os: dgt_os.state == 'under_repair'):
			raise UserError(_('O.S. já em execução.'))
		# TODO
		# - verificar se existe peça
		# - se existir ir para ender_repair e realizar pedido ao estoque
		# - senao existir ir para 'esperando peças' e realizar a inclusão no pedido de compras
		# - 
		pecas_faltando = []
		for pecas in self.pecas:
			if pecas.qty_available <  pecas.product_uom_qty:
				pecas_faltando = pecas.id
		if pecas_faltando:
			return self.write({'state': 'released'})
		return self.write({'state': 'under_repair'})

		
	
	@api.multi
	def action_repair_cancel(self):
		if self.filtered(lambda dgt_os: dgt_os.state == 'done'):
			raise UserError(_("Cannot cancel completed repairs."))
		if any(dgt_os.invoiced for dgt_os in self):
			raise UserError(_('Repair order is already invoiced.'))
		self.mapped('pecas').write({'state': 'cancel'})
		return self.write({'state': 'cancel'})
		
	@api.multi
	def action_repair_invoice_create(self):
		self.action_invoice_create()
		if self.invoice_method == 'b4repair':
			self.action_repair_ready()
		elif self.invoice_method == 'after_repair':
			self.write({'state': 'done'})
		return True
	
	@api.multi
	def action_invoice_create(self, group=False):
		""" Creates invoice(s) for repair order.
		@param group: It is set to true when group invoice is to be generated.
		@return: Invoice Ids.
		"""
		res = dict.fromkeys(self.ids, False)
		invoices_group = {}
		InvoiceLine = self.env['account.invoice.line']
		Invoice = self.env['account.invoice']
		InvoiceLineServ = self.env['account.invoice.line']
		InvoiceServ = self.env['account.invoice']
		for dgt_os in self.filtered(lambda dgt_os: dgt_os.state not in ('draft', 'cancel') and not (dgt_os.invoice_id or dgt_os.invoice_servico_id)):
			if not dgt_os.cliente_id.id and not dgt_os.partner_invoice_id.id:
				raise UserError(_('Você deve selecionar um Cliente para realizar o faturamento!'))
			comment = dgt_os.quotation_notes
			if dgt_os.invoice_method != 'none':
				if group and dgt_os.partner_invoice_id.id in invoices_group:
					invoice = invoices_group[dgt_os.partner_invoice_id.id]
					invoice.write({
						'name': invoice.name + ', ' + dgt_os.name,
						'origin': invoice.origin + ', ' + dgt_os.name,
						'comment': (comment and (invoice.comment and invoice.comment + "\n" + comment or comment)) or (invoice.comment and invoice.comment or ''),
					})
				else:
					if not dgt_os.cliente_id.property_account_receivable_id:
						raise UserError(_('No account defined for partner "%s".') % dgt_os.cliente_id.name)
					pecas_to_invoice = dgt_os.pecas.filtered(lambda pecas: pecas.to_invoice) 
					servicos_to_invoice = dgt_os.servicos.filtered(lambda servicos: servicos.to_invoice)
					if not pecas_to_invoice and not servicos_to_invoice:
						raise UserError(_('Não há peças nem serviços para faturar. Favor adicionar pelo menos um item de peça ou serviço'))
					if pecas_to_invoice:
						invoice_peca = Invoice.create({
							'name': dgt_os.name + u'/P',
							'origin': dgt_os.name,
							'type': 'out_invoice',
							'account_id': dgt_os.cliente_id.property_account_receivable_id.id,
							'partner_id': dgt_os.partner_invoice_id.id or dgt_os.cliente_id.id,
							'currency_id': dgt_os.pricelist_id.currency_id.id,
							'comment': dgt_os.quotation_notes,
							'fiscal_position_id': dgt_os.cliente_id.property_account_position_id.id
						})
						dgt_os.write({'invoiced': True, 'invoice_id': invoice_peca.id})
					#invoices_group[dgt_os.partner_invoice_id.id] = invoice_peca
					if servicos_to_invoice:
						 
						invoice_servico = InvoiceServ.create({
							'name': dgt_os.name + u'/S',
							'origin': dgt_os.name,
							'type': 'out_invoice',
							'account_id': dgt_os.cliente_id.property_account_receivable_id.id,
							'partner_id': dgt_os.partner_invoice_id.id or dgt_os.cliente_id.id,
							'currency_id': dgt_os.pricelist_id.currency_id.id,
							'comment': dgt_os.quotation_notes,
							'fiscal_position_id': dgt_os.cliente_id.property_account_position_id.id,
							'fiscal_document_id': self.env['br_account.fiscal.document'].search([('name','ilike','Nota Fiscal Avulsa')])[0].id,
							'document_serie_id': self.env['br_account.document.serie'].search([('name','ilike','Série 1 - Nota Avulsa')])[0].id,
						})
						dgt_os.write({'invoiced': True, 'invoice_servico_id': invoice_servico.id})
				
				
				for pecas in pecas_to_invoice:
					if group:
						name = dgt_os.name + '-' + pecas.name
					else:
						name = pecas.name
					if pecas.product_id.property_account_income_id:
						account_id = pecas.product_id.property_account_income_id.id
					elif pecas.product_id.categ_id.property_account_income_categ_id:
						account_id = pecas.product_id.categ_id.property_account_income_categ_id.id
					else:
						raise UserError(_('No account defined for product "%s".') % pecas.product_id.name)
					
					invoice_line = InvoiceLine.create({
						'invoice_id': invoice_peca.id,
						'name': name,
						'origin': dgt_os.name,
						'account_id': account_id,
						'quantity': pecas.product_uom_qty,
						'invoice_line_tax_ids': [(6, 0, [x.id for x in pecas.tax_id])],
						'uom_id': pecas.product_uom.id,
						'price_unit': pecas.price_unit,
						'price_subtotal': pecas.product_uom_qty * pecas.price_unit,
						'product_id': pecas.product_id and pecas.product_id.id or False,
						'fiscal_classification_id': pecas.product_id.fiscal_classification_id.id,
						'account_analytic_id':dgt_os.account_analytic_id.id,
					})
					pecas.write({'invoiced': True, 'invoice_line_id': invoice_line.id})
				if pecas_to_invoice:	
					invoice_peca.compute_taxes()
					res[dgt_os.id] = invoice_peca.id
				for servicos in servicos_to_invoice:
					if group:
						name = dgt_os.name + '-' + servicos.name
					else:
						name = servicos.name
					if servicos.product_id.property_account_income_id:
						account_id = servicos.product_id.property_account_income_id.id
					elif servicos.product_id.categ_id.property_account_income_categ_id:
						account_id = servicos.product_id.categ_id.property_account_income_categ_id.id
					else:
						raise UserError(_('No account defined for product "%s".') % servicos.product_id.name)
					
					invoice_line_serv = InvoiceLineServ.create({
						'invoice_id': invoice_servico.id,
						'name': name,
						'origin': dgt_os.name,
						'account_id': account_id,
						'quantity': servicos.product_uom_qty,
						'invoice_line_tax_ids': [(6, 0, [x.id for x in servicos.tax_id])],
						'uom_id': servicos.product_uom.id,
						'price_unit': servicos.price_unit,
						'price_subtotal': servicos.product_uom_qty * servicos.price_unit,
						'product_id': servicos.product_id and servicos.product_id.id or False,
						'account_analytic_id':dgt_os.account_analytic_id.id,
					})
					servicos.write({'invoiced': True, 'invoice_line_id': invoice_line_serv.id})
				if servicos_to_invoice:
					invoice_servico.compute_taxes()
					res[dgt_os.id] = invoice_servico.id	
		return res
	
	@api.multi
	def action_repair_ready(self):
		self.mapped('pecas').write({'state': 'confirmed'})
		return self.write({'state': 'ready'})
	
	@api.multi
	def action_repair_start(self):
		""" Writes repair order state to 'Under Repair'
		@return: True
		"""
		if self.filtered(lambda dgt_os: dgt_os.state not in ['confirmed', 'ready']):
			raise UserError(_("Repair must be confirmed before starting reparation."))
		self.mapped('pecas').write({'state': 'confirmed'})
		return self.write({'state': 'under_repair'})
		
					
	@api.multi
	def action_repair_end(self):
		""" Writes repair order state to 'To be invoiced' if invoice method is
		After repair else state is set to 'Ready'.
		@return: True
		"""
		if self.filtered(lambda dgt_os: dgt_os.state != 'under_repair'):
			raise UserError(_("A ordem de serviço de estar \"em execução\" para finalizar a execução."))
		if self.pecas:
			for peca in self.pecas:
				if not peca.aplicada:
					raise UserError(_("Todas as peças devem estar aplicadas para finalizar a Ordem de Serviço."))
		sem_relatorio = True			
		for relatorio in self.relatorios:
			sem_relatorio = False
			sem_atendimento = True
			for atendimento in relatorio.atendimentos:
				sem_atendimento = False
				for dgt_os in self:
					dgt_os.write({'repaired': True})
					vals = {
							'state': 'done',
							'time_execution':relatorio.time_execution,
							'date_execution': time.strftime('%Y-%m-%d %H:%M:%S'),
					}
					#vals['moves_id'] = dgt_os.action_repair_done().get(dgt_os.id)
					dgt_os.action_repair_done()
					if not dgt_os.invoiced and dgt_os.invoice_method == 'after_repair':
						vals['state'] = '2binvoiced'
					dgt_os.write(vals)
			if sem_atendimento:
				raise UserError(_("Para finalizar O.S. deve-se preencher os horários de atendimento de início e fim do serviço."))
				return False
		if sem_relatorio:	
			raise UserError(_("Para finalizar O.S. deve-se incluir pelo menos um relatório de serviço."))
			return False
		return True
		
	@api.multi
	def action_repair_reprovar(self):
		if self.filtered(lambda dgt_os: dgt_os.state == 'reprovado'):
			raise UserError(_("A ordem de serviço de já está reprovada."))
		self.write({'state': 'reprovado'})
		
	
	
	@api.multi
	def action_repair_done(self):
		""" Creates stock move for operation and stock move for final product of repair order.
		@return: Move ids of final products
		"""
		if self.filtered(lambda dgt_os: not dgt_os.repaired):
			raise UserError(_("Repair must be repaired in order to make the product moves."))
		if self.pecas:
			for peca in self.pecas:
				if not peca.aplicada:
					raise UserError(_("Todas as peças devem estar aplicadas para finalizar a Ordem de Serviço."))
					
		res = {}
		Move = self.env['stock.move']
		for dgt_os in self:
			moves = self.env['stock.move']
			for operation in dgt_os.pecas:
				move = Move.create({
					'name': operation.name,
					'product_id': operation.product_id.id,
					'restrict_lot_id': operation.lot_id.id,
					'product_uom_qty': operation.product_uom_qty,
					'product_uom': operation.product_uom.id,
					'partner_id': dgt_os.address_id.id,
					'location_id': operation.location_id.id,
					'location_dest_id': operation.location_dest_id.id,
				})
				moves |= move
				operation.write({'move_id': move.id, 'state': 'done'})
			moves.action_done()
		return res
	def action_done(self):
		self.verifica_pecas_aplicadas(self)
		self.write({'state': 'done','repaired':'True', 'date_execution': time.strftime('%Y-%m-%d %H:%M:%S')})
		return True
		
	def force_done(self):
		self.force_parts_reservation()
		wf_service = netsvc.LocalService("workflow")
		for order in self:
			wf_service.trg_validate(self.env.user.id, 'dgt_os.os', order.id, 'action_repair_start', self.env.cr)
		return self.write({'state': 'under_repair'})
		
	def force_parts_reservation(self):
		for order in self:
			order.pecas_ready_lines.force_assign()
		return True	
		
class dgtOsPecasLine(models.Model):
	_name = 'dgt_os.os.pecas.line'
	_description = u'Ordem de Serviço Peças Planejadas Line'
	_order = 'os_id, sequence, id'
	
	name = fields.Char('Descrição', size=64)
	os_id = fields.Many2one(
		'dgt_os.os', 'Repair Order Reference',
		index=True, ondelete='cascade')
	aplicada = fields.Boolean('Aplicada', copy=False)
	to_invoice = fields.Boolean('Faturar')
	product_id = fields.Many2one('product.product', u'Peças', required=True)
	invoiced = fields.Boolean('Faturada', copy=False, readonly=True)
	price_unit = fields.Float('P. Unit', required=True, digits=dp.get_precision('Product Price'))
	price_subtotal = fields.Float('Subtotal',
		compute='_compute_price_subtotal',
		digits=dp.get_precision('Product Price'))
	price_subtotal_no_invoiced = fields.Float('Subtotal',
		compute='_compute_price_subtotal',
		digits=dp.get_precision('Product Price'))
	tax_id = fields.Many2many(
		'account.tax', 'dgt_os_pecas_line_tax', 'dgt_os_pecas_line_id', 'tax_id', 'Impostos')
	#product_qty = fields.Float(
	#	'Qtd', default=1.0,
	#	 required=True)
	product_uom_qty = fields.Float(
		'Qtd', default=1.0,
		digits=dp.get_precision('Product Unit of Measure'), required=True)
	product_uom = fields.Many2one(
		'product.uom', 'Unidade de medida',
		required=True) 
	qty_available = fields.Float(
        'Quantity On Hand',compute = '_compute_peca_disponivel',
        digits=dp.get_precision('Product Unit of Measure'),
        help="Current quantity of products.\n"
             "In a context with a single Stock Location, this includes "
             "goods stored at this Location, or any of its children.\n"
             "In a context with a single Warehouse, this includes "
             "goods stored in the Stock Location of this Warehouse, or any "
             "of its children.\n"
             "stored in the Stock Location of the Warehouse of this Shop, "
             "or any of its children.\n"
             "Otherwise, this includes goods stored in any Stock Location "
             "with 'internal' type.",readonly=True, copy=False)
	invoice_line_id = fields.Many2one(
		'account.invoice.line', 'Linha da fatura',
		copy=False, readonly=True)
	location_id = fields.Many2one(
		'stock.location', 'Origem',
		index=True, required=False)
	location_dest_id = fields.Many2one(
		'stock.location', 'Destino',
		index=True, required=False)
	move_id = fields.Many2one(
		'stock.move', 'Movimeto Estoque',
		copy=False, readonly=True)
	lot_id = fields.Many2one('stock.production.lot', 'Lote')
	sequence = fields.Integer(string='Sequence', default=10)
	@api.one
	@api.depends('to_invoice', 'price_unit', 'os_id', 'product_uom_qty', 'product_id')
	def _compute_price_subtotal(self):
		taxes = self.env['account.tax'].compute_all(self.price_unit, self.os_id.pricelist_id.currency_id, self.product_uom_qty, self.product_id, self.os_id.cliente_id)
		if not self.to_invoice:
			self.price_subtotal = 0.0
			self.price_subtotal_no_invoiced = taxes['total_excluded']
		else:
			self.price_subtotal = taxes['total_excluded']
			self.price_subtotal_no_invoiced = 0.0
	
	@api.one
	@api.depends('product_uom_qty', 'product_id')
	def _compute_peca_disponivel(self):
		self.qty_available  = self.product_id.qty_available
		
	#@api.onchange('type', 'os_id')
	def onchange_operation_type(self):
		""" On change of operation type it sets source location, destination location
		and to invoice field.
		@param product: Changed operation type.
		@param guarantee_limit: Guarantee limit of current record.
		@return: Dictionary of values.
		"""
		if not self.type:
			self.location_id = False
			self.Location_dest_id = False
		elif self.type == 'add':
			args = self.os_id.company_id and [('company_id', '=', self.os_id.company_id.id)] or []
			warehouse = self.env['stock.warehouse'].search(args, limit=1)
			self.location_id = warehouse.lot_stock_id
			self.location_dest_id = self.env['stock.location'].search([('usage', '=', 'production')], limit=1).id
			self.to_invoice = self.os_id.guarantee_limit and datetime.strptime(self.os_id.guarantee_limit, '%Y-%m-%d') < datetime.now()
		else:
			self.location_id = self.env['stock.location'].search([('usage', '=', 'production')], limit=1).id
			self.location_dest_id = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1).id
			self.to_invoice = False
	
	@api.onchange('os_id', 'product_id', 'product_uom_qty')
	def onchange_product_id(self):
		""" On change of product it sets product quantity, tax account, name,
		uom of product, unit price and price subtotal. """
		partner = self.os_id.cliente_id
		pricelist = self.os_id.pricelist_id
		args = self.os_id.company_id and [('company_id', '=', self.os_id.company_id.id)] or []
		warehouse = self.env['stock.warehouse'].search(args, limit=1)
		self.location_id = warehouse.lot_stock_id
		self.location_dest_id = self.env['stock.location'].search([('usage', '=', 'production')], limit=1).id
		#self.to_invoice = self.os_id.guarantee_limit and datetime.strptime(self.os_id.guarantee_limit, '%Y-%m-%d') < datetime.now()
		if not self.product_id or not self.product_uom_qty:
			return
		if partner and self.product_id:
			self.tax_id = partner.property_account_position_id.map_tax(self.product_id.taxes_id).ids
		if self.product_id:
			self.name = self.product_id.display_name
			self.product_uom = self.product_id.uom_id.id
			self.qty_available = self.product_id.qty_available
		warning = False
		if not pricelist:
			warning = {
				'title': _('No Pricelist!'),
				'message':
					_('Selecione uma lista de preço!\n Antes de escolhe uma peça.')}
		else:
			price = pricelist.get_product_price(self.product_id, self.product_uom_qty, partner)
			if price is False:
				warning = {
					'title': _('Não encontrado nenhuma lista de preço válida !'),
					'message':
						_("Couldn't find a pricelist line matching this product and quantity.\nYou have to change either the product, the quantity or the pricelist.")}
			else:
				self.price_unit = price
		if warning:
			return {'warning': warning}
		
class ServicosLine(models.Model):
	_name = 'dgt_os.os.servicos.line'
	_description = 'Servicos Line'
	_order = 'os_id, sequence, id'
	
	name = fields.Char('Description', required=True)
	os_id = fields.Many2one(
		'dgt_os.os', 'Ordem de Serviço',
		index=True, ondelete='cascade')
	to_invoice = fields.Boolean('Faturar')
	product_id = fields.Many2one('product.product', u'Serviço',domain=[('type','=','service')], required=True)
	invoiced = fields.Boolean('Faturada', copy=False, readonly=True)
	price_unit = fields.Float('P. Unit', required=True, digits=dp.get_precision('Product Price'))
	price_subtotal = fields.Float('Subtotal',
		compute='_compute_price_subtotal',
		digits=0)
	price_subtotal_no_invoiced = fields.Float('Subtotal Não faturado',
		compute='_compute_price_subtotal',
		digits=0)
	tax_id = fields.Many2many(
		'account.tax', 'dgt_os_service_line_tax', 'dgt_os_service_line_id', 'tax_id', 'Impostos')
	product_uom_qty = fields.Float(
		'Qtd', default=1.0,
		digits=dp.get_precision('Product Unit of Measure'), required=True)
	product_uom = fields.Many2one(
		'product.uom', 'Unidade de medida',
		required=True)
	invoice_line_id = fields.Many2one(
		'account.invoice.line', 'Linha da fatura',
		copy=False, readonly=True)
	sequence = fields.Integer(string='Sequence', default=10)
	
	
	@api.one
	@api.depends('to_invoice', 'price_unit', 'os_id', 'product_uom_qty', 'product_id')
	def _compute_price_subtotal(self):
		taxes = self.env['account.tax'].compute_all(self.price_unit, self.os_id.pricelist_id.currency_id, self.product_uom_qty, self.product_id, self.os_id.cliente_id)
		if not self.to_invoice:
			self.price_subtotal = 0.0
			self.price_subtotal_no_invoiced = taxes['total_excluded']
		else:
			self.price_subtotal = taxes['total_excluded']
			self.price_subtotal_no_invoiced = 0.0
			
	@api.onchange('os_id', 'product_id', 'product_uom_qty')
	def onchange_product_id(self): 
		""" On change of product it sets product quantity, tax account, name,
		uom of product, unit price and price subtotal. """
		partner = self.os_id.cliente_id
		pricelist = self.os_id.pricelist_id
		
		if not self.product_id or not self.product_uom_qty:
			return
		if partner and self.product_id:
			self.tax_id = partner.property_account_position_id.map_tax(self.product_id.taxes_id).ids
		if self.product_id:
			self.name = self.product_id.display_name
			self.product_uom = self.product_id.uom_id.id
		warning = False
		if not pricelist:
			warning = {
				'title': _('No Pricelist!'),
				'message':
					_('Selecione uma lista de preço!\n Antes de escolhe uma peça.')}
		else:
			price = pricelist.get_product_price(self.product_id, self.product_uom_qty, partner)
			if price is False:
				warning = {
					'title': _('Não encontrado nenhuma lista de preço válida !'),
					'message':
						_("Couldn't find a pricelist line matching this product and quantity.\nYou have to change either the product, the quantity or the pricelist.")}
			else:
				self.price_unit = price
		if warning:
			return {'warning': warning}
			
			

class RelatoriosServico(models.Model):
	_name = 'dgt_os.os.relatorio.servico'	
	_inherit = ['mail.thread']
	#name = fields.Char('Nº Relatório de Serviço', required=True)
	name = fields.Char(
		'Nº Relatório de Serviço',default=lambda self: self.env['ir.sequence'].next_by_code('dgt_os.os.relatorio'),
		copy=False, required=True)
	os_id = fields.Many2one(
		'dgt_os.os', 'Ordem de serviço',
		index=True, ondelete='cascade')
	cliente_id = fields.Many2one('res.partner', string='Owner',
		compute='_compute_relatorio_default',
		track_visibility='onchange',store=True)
	relatorio_num = fields.Char('Nº Relatório')
	equipment_id = fields.Many2one(
		'maintenance.equipment','Equipamento',
		compute='_compute_relatorio_default',
		store=True,
		index=True,
		help='Escolha o equipamento referente ao Relatorio de Servico.')
	tecnicos_id = fields.Many2many(
		'hr.employee',
		#compute='_compute_relatorio_default',
		#inverse='_set_tecnicos_id',
		
		string = 'Técnicos')
	motivo_chamado = fields.Text('Descreva o motivo do chamado')
	defeitos = fields.Text('Descreva tecnicamente o defeito apresentado')
	servico_executados = fields.Text('Descreva o serviço realizado')
	pendencias = fields.Text('Descreva pendências')
	atendimentos = fields.One2many(
		'dgt_os.os.relatorio.atendimento.line', 'relatorio_id', 'Atendimento',
		required=True, readonly=False)
	time_execution = fields.Float(String='tempo execução',compute='_compute_time_execution', store=True )
	
	@api.onchange('tecnicos_id')
	def onchange_tecnicos_id(self):
		self.os_id.tecnicos_id = self.tecnicos_id
		
	#@api.multi
	#@api.onchange('atendimentos')
	# def onchange_atendimentos(self):
		# time = 0.0
		# #if self.atendimentos:
		# for atendimento in self.atendimentos:
			# if atendimento.data_ini and atendimento.data_fim:
				# data_fim = atendimento.data_fim
				# data_ini = atendimento.data_ini
				# datetimeFormat = '%Y-%m-%d %H:%M:%S' 
				# fim = datetime.strptime(data_fim,datetimeFormat)
				# ini = datetime.strptime(data_ini,datetimeFormat)
				# timedelta = fim - ini
				# #hour1 = timedelta.seconds
				# #hours = (timedelta.seconds) / 3600
				# minutos = (timedelta.seconds) / 60
				# time = time + minutos;
		# self.time_execution = time/60

	
	@api.depends('atendimentos')
	def _compute_time_execution(self):
		time = 0.0
		for rel in self:
			for atendimento in rel.atendimentos:
				if atendimento.data_ini and atendimento.data_fim:
					data_fim = atendimento.data_fim
					data_ini = atendimento.data_ini
					datetimeFormat = '%Y-%m-%d %H:%M:%S' 
					fim = datetime.strptime(data_fim,datetimeFormat)
					ini = datetime.strptime(data_ini,datetimeFormat)
					timedelta = fim - ini
					#hour1 = timedelta.seconds
					#hours = (timedelta.seconds) / 3600
					minutos = (timedelta.seconds) / 60
					time = time + minutos;
			rel.update({ 'time_execution' : time/60})
		
			
	@api.one
	@api.depends('os_id','os_id.cliente_id','os_id.equipment_id','os_id.tecnicos_id')
	def _compute_relatorio_default(self):
		self.cliente_id = self.os_id.cliente_id.id
		self.equipment_id = self.os_id.equipment_id.id
		#self.tecnicos_id = self.os_id.tecnicos_id
		
class RelatoriosAtendimentoLines(models.Model):
	_name = "dgt_os.os.relatorio.atendimento.line"
	
	name = fields.Char('Item',readonly=True)
	relatorio_id = fields.Many2one(
		'dgt_os.os.relatorio.servico', 'Repair Order Reference',
		index=True,  ondelete='cascade')
	data_ini = fields.Datetime(string='Data de Início',  required=True,
		help='Data de inicio do servico')
	data_fim = fields.Datetime(string='Data de Fim', required=True,
		help='Data de fim do servico')

class dgtOsTask(models.Model):
	"""
	Ordem de serviço Tarefas 
	"""
	_name = 'dgt_os.os.task'
	_description = 'Tarefa de Serviço'

	MAINTENANCE_TYPE_SELECTION = [
		('cm', 'Corrective')
	]

	name = fields.Char('Descrição', size=64, required=True, translate=True)
	category_id = fields.Many2one('maintenance.equipment.category', 'Categoria do Equipamento', ondelete='restrict', required=True)
	maintenance_type = fields.Selection(MAINTENANCE_TYPE_SELECTION, 'Tipo de Manutenção', required=True, default='corrective')
	pecas_lines = fields.One2many('dgt_os.os.task.pecas.line', 'task_id', 'Parts')
	tools_description = fields.Text('Descrição das Ferramentas',translate=True)
	labor_description = fields.Text('Descrição dos Ensaios',translate=True)
	operations_description = fields.Text('Descriççao das operações',translate=True)
	documentation_description = fields.Text('Descrição da Documentação',translate=True)
	active = fields.Boolean('Active', default=True)


class dgtOsTaskPecasLine(models.Model):
	_name = 'dgt_os.os.task.pecas.line'
	_description = 'Peças'

	name = fields.Char('Descrição', size=64)
	pecas_id = fields.Many2one('product.product', 'Pecas', required=True)
	pecas_qty = fields.Float('Quantidade', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
	pecas_uom = fields.Many2one('product.uom', 'Unidade', required=True)
	task_id = fields.Many2one('dgt_os.os.task', 'Tarefas da OS')

	@api.onchange('pecas_id')
	def onchange_parts(self):
		self.pecas_uom = self.pecas_id.uom_id.id

	def unlink(self):
		self.write({'task_id': False})
		return True

	@api.model
	def create(self, values):
		ids = self.search([('task_id','=',values['task_id']),('pecas_id','=',values['pecas_id'])])
		if len(ids)>0:
			values['pecas_qty'] = ids[0].pecas_qty + values['pecas_qty']
			ids[0].write(values)
			return ids[0]
		ids = self.search([('task_id','=',False)])
		if len(ids)>0:
			ids[0].write(values)
			return ids[0]
		return super(dgtOsTaskPecasLine, self).create(values)
		
class dgtMotivoReprova(models.Model):
	_name = "dgt_os.os.motivo.reprova"
	_description = u'Motivos de reprovação da Ordem de serviço'
	
	name = fields.Char('Name', required=True, translate=True)
	active = fields.Boolean('Active', default=True)