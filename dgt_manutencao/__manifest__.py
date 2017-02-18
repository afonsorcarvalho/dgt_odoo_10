# -*- coding: utf-8 -*-
{
    'name': "Diagnóstica Manutenção",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Engº Afonso Carvalho",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','mail','maintenance','hr'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
#		'data/dgt_manutencao_data.xml',
#		'data/dgt_manutencao_cron.xml',
        'views/dgt_manutencao_templates.xml',
		'views/dgt_manutencao_views.xml'
        
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
	'installable': True,
    'auto_install': False,
    'application': False,
}