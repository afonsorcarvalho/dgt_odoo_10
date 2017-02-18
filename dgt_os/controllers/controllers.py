# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class DgtOs(http.Controller):
	@http.route('/dgt_os/os', type='http', auth='public')
	def os(self):
		records = request.env['dgt_os.os'].sudo().search([])
		result = '<html><body><table><tr><td>'
		result += '</td></tr><tr><td>'.join(records.mapped('name'))
		result += '<td></tr></table></body></html>'
		return result
#     @http.route('/dgt_os/dgt_os/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('dgt_os.listing', {
#             'root': '/dgt_os/dgt_os',
#             'objects': http.request.env['dgt_os.dgt_os'].search([]),
#         })

#     @http.route('/dgt_os/dgt_os/objects/<model("dgt_os.dgt_os"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dgt_os.object', {
#             'object': obj
#         })