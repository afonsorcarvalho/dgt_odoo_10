# -*- coding: utf-8 -*-
{
    'name': "Ordem de Serviço",
	'version': '1.0',
    'sequence': 200,
    'category': 'AT',
    'summary': 'Gerenciamento de Assistência Técnica',

    'summary': """
        Módulo de gerenciamento de assistência técnica com solicitação de serviço e ordem de serviço
        """,

    'description': """
        Long description of module's purpose
    """,

    'author': "Engº Afonso Carvalho",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
   
    # any module necessary for this one to work correctly
    'depends': ['base','mro','sale','stock', 'account','maintenance','br_nfe','br_nfse','br_account','br_account_einvoice'],

    # always loaded 
    'data': [
        'security/ir.model.access.csv',
		'security/at_security.xml',
		'views/dgt_os_motivo_reprova.xml',
		'views/dgt_os_view.xml',
		'views/dgt_os_request_view.xml',
		'views/reports.xml',
#		'views/asset_view.xml',
		'views/report_ordem_servico.xml',
		'views/report_orcamento_servico.xml',
		'data/ir_sequence_data.xml',
#	'views/dgt_os_views.xml',
#       'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
	'installable': True,
    'auto_install': False,
    'application': True,
}
