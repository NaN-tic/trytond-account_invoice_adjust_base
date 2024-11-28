from collections import defaultdict
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

class Line(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    adjust_base = fields.Boolean('Adjust Base')

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

        bases = defaultdict(lambda: 0)

        for line in invoice.taxes:
            bases[line.tax.id] -= line.base
        for line in self.start.tax_lines:
            if bases.get(line.tax.id):
                bases[line.tax.id] += line.base

        existent_adjust_lines_dict = {line.taxes[0].id:
            line for line in invoice.lines if line.adjust_base}
        for tax, base in bases.items():
            if existent_adjust_lines_dict.get(tax):
                adjust_line = existent_adjust_lines_dict[tax]
                adjust_line.unit_price += base
            else:
                adjust_line = InvoiceLine()
                adjust_line.invoice = invoice
                adjust_line.type = 'line'
                adjust_line.unit_price = base
                adjust_line.account = (
                    AccountConfiguration(1).default_category_account_expense)
                adjust_line.quantity = 1
                adjust_line.taxes = [line.tax]
                adjust_line.adjust_base = True
            adjust_line.save()
            if adjust_line.unit_price == 0:
                InvoiceLine.delete([adjust_line])
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