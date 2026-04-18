# -*- coding: utf-8 -*-

{
    'name': "Connector Fintoc",

    'summary': """
        Get bank statements from Fintoc
    """,

    'author': "Blueminds",
    'website': "https://www.blueminds.cl",

    'category': 'Accounting/Accounting',
    'version': '0.1',

    'depends': [
        'account',
    ],
    'data': [
        'views/account_bank_statement.xml',
        'views/res_bank_view.xml',
        'views/res_company.xml',
        'data/cron.xml',
    ],

    'demo': [
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'GPL-3',
}
