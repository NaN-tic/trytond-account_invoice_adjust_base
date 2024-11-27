from trytond.pool import PoolMeta, Pool
from trytond.model import fields, ModelView
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateView, StateTransition, Button



class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._buttons.update({
            'adjust_base': {
                'invisible': ~Eval('state').in_(['draft']) | (Eval('type') != 'in'),
                'depends': ['state', 'type'],
            },
        })


    @classmethod
    @ModelView.button_action('account_invoice_adjust_base.wizard_adjust_base')
    def adjust_base(cls, invoices):
        pass


class AdjustBase(Wizard):
    'Adjust base'
    __name__ = 'account.invoice.wizard_adjust_base'
    start = StateView('account.invoice.wizard_adjust_base.start',
        'account_invoice_adjust_base.wizard_adjust_base_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Modify', 'modify_', 'tryton-ok', default=True),
        ])
    check = StateView('account.invoice.wizard_adjust_base.check',
            'account_invoice_adjust_base.wizard_adjust_base_check_view_form', [
        Button('Ok', 'end', 'tryton-ok'),
    ])
    modify_ = StateTransition()

    def transition_modify_(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        AccountConfiguration = pool.get('account.configuration')
        invoice = self.record

        for line in self.start.tax_lines:
            for tax_line in invoice.taxes:
                if tax_line.tax == line.tax:
                    if tax_line.base != line.base:
                        amount = line.base - tax_line.base
                        new_line = InvoiceLine()
                        new_line.invoice = invoice
                        new_line.unit_price = amount
                        new_line.type = 'line'
                        new_line.account = AccountConfiguration(1).default_category_account_expense
                        new_line.quantity = 1
                        new_line.taxes = [line.tax]
                        new_line.save()
                    break
        invoice.update_taxes()
        invoice.save()
        return 'check'

    def default_start(self, fields):
        invoice = self.record
        tax_lines = []

        for tax_line in invoice.taxes:
            tax_lines.append({
                'tax': tax_line.tax.id,
                'tax.rec_name': tax_line.tax.rec_name,
                'base': tax_line.base,
            })
        defaults = {}
        defaults['tax_lines'] = tax_lines
        return defaults

    def default_check(self, fields):
        return {
            'taxes': [i.id for i in self.record.taxes],
        }


class AdjustBaseStart(ModelView):
    'Adjust Base Start'
    __name__ = 'account.invoice.wizard_adjust_base.start'
    tax_lines = fields.One2Many('account.invoice.wizard_adjust_base.line', None, 'Tax Lines', required=True)


class AdjustBaseLine(ModelView):
    'Adjust Base Line'
    __name__ = 'account.invoice.wizard_adjust_base.line'
    tax = fields.Many2One('account.tax', 'Tax', required=True)
    base = fields.Numeric('Base', required=True)


class AdjustBaseCheck(ModelView):
    'Adjust Base Check'
    __name__ = 'account.invoice.wizard_adjust_base.check'
    taxes = fields.One2Many('account.invoice.tax', None, 'Taxes', readonly=True)