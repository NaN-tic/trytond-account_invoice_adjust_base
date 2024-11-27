import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
    create_fiscalyear, create_tax, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install account_invoice_taxes_required Module
        activate_modules('account_invoice_adjust_base')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create account categories
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()
        account_category_tax, = account_category.duplicate()
        account_category_tax.supplier_taxes.append(tax)
        account_category_tax.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('1000')
        template.account_category = account_category_tax
        product, = template.products
        product.cost_price = Decimal('25')
        template.save()
        product, = template.products

        # Create invoice
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = party
        line = invoice.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal(1000)
        line.account = expense
        invoice.save()
        invoice.reload()

        # Start the wizard
        adjust = Wizard('account.invoice.wizard_adjust_base', [invoice])
        self.assertEqual(len(adjust.form.tax_lines), len(invoice.taxes))
        original_tax_line = invoice.taxes[0]

        # Verify default tax line matches invoice
        wizard_tax_line = adjust.form.tax_lines[0]
        self.assertEqual(wizard_tax_line.tax, original_tax_line.tax)
        self.assertEqual(wizard_tax_line.base, original_tax_line.base)

        # Modify tax base in wizard
        adjust.form.tax_lines[0].base = Decimal(500)
        adjust.execute('modify_')

        # Check that a new adjustment line is created correctly
        adjustment_line = invoice.lines[1]
        self.assertEqual(adjustment_line.unit_price, Decimal('-500'))
        self.assertEqual(adjustment_line.account, expense)

        # Create invoice
        invoice2 = Invoice()
        invoice2.type = 'in'
        invoice2.party = party
        line = invoice2.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal(1000)
        line.account = expense
        invoice2.save()
        invoice2.reload()

        # Start the wizard
        adjust = Wizard('account.invoice.wizard_adjust_base', [invoice2])
        self.assertEqual(len(adjust.form.tax_lines), len(invoice2.taxes))
        original_tax_line = invoice2.taxes[0]

        # Verify default tax line matches invoice
        wizard_tax_line = adjust.form.tax_lines[0]
        self.assertEqual(wizard_tax_line.tax, original_tax_line.tax)
        self.assertEqual(wizard_tax_line.base, original_tax_line.base)

        # Modify tax base in wizard
        adjust.form.tax_lines[0].base = Decimal(1500)
        adjust.execute('modify_')

        # Check that a new adjustment line is created correctly
        adjustment_line = invoice2.lines[1]
        self.assertEqual(adjustment_line.unit_price, Decimal('500'))
        self.assertEqual(adjustment_line.account, expense)