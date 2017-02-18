# -*- coding: utf-8 -*-
from odoo import http

# class DgtManutencao(http.Controller):
#     @http.route('/dgt_manutencao/dgt_manutencao/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dgt_manutencao/dgt_manutencao/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('dgt_manutencao.listing', {
#             'root': '/dgt_manutencao/dgt_manutencao',
#             'objects': http.request.env['dgt_manutencao.dgt_manutencao'].search([]),
#         })

#     @http.route('/dgt_manutencao/dgt_manutencao/objects/<model("dgt_manutencao.dgt_manutencao"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dgt_manutencao.object', {
#             'object': obj
#         })