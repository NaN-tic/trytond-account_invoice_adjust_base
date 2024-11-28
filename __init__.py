# This file is part account_invoice_adjust_base module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import invoice

def register():
    Pool.register(
        invoice.Invoice,
        invoice.Line,
        invoice.AdjustBaseStart,
        invoice.AdjustBaseLine,
        invoice.AdjustBaseCheck,
        module='account_invoice_adjust_base', type_='model')
    Pool.register(
        invoice.AdjustBase,
        module='account_invoice_adjust_base', type_='wizard')
