import datetime as dt
from types import SimpleNamespace
from proteus import Model
from decimal import Decimal
from trytond.tests.tools import activate_modules, set_user
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.account.tests.tools import (
    create_chart, create_fiscalyear, get_accounts)
from trytond.modules.account_es.tests.tools import get_tax

def setup():
    vars = SimpleNamespace()

    vars.config = activate_modules('account_invoice_adjust_base')

    _ = create_company()
    vars.company = get_company()

    # Set employee
    User = Model.get('res.user')
    Party = Model.get('party.party')
    Employee = Model.get('company.employee')

    employee_party = Party(name="Employee")
    employee_party.save()
    vars.employee = Employee(party=employee_party)
    vars.employee.save()

    Location = Model.get('stock.location')
    vars.warehouse, = Location.find([('code', '=', 'WH')])

    # Set user
    vars.user = User(vars.config.user)
    vars.user.company = vars.company
    vars.user.employees.append(vars.employee)
    vars.user.employee = vars.employee
    vars.user.warehouse = vars.warehouse
    vars.user.save()
    set_user(vars.user.id)

    # Create fiscal year
    fiscalyear = set_fiscalyear_invoice_sequences(
        create_fiscalyear(vars.company))
    fiscalyear.click('create_period')

    # Create chart of accounts
    _ = create_chart(vars.company, chart='account_es.pgc_0')
    accounts = get_accounts(vars.company)
    vars.revenue = accounts['revenue']
    vars.expense = accounts['expense']
    vars.payable = accounts['payable']

    # Get taxes
    vars.customer_vat_10 = get_tax('iva_rep_10', vars.company)
    vars.customer_vat_21 = get_tax('iva_rep_21', vars.company)
    vars.supplier_vat_10 = get_tax('iva_sop_10', vars.company)
    vars.supplier_vat_21 = get_tax('iva_sop_21', vars.company)

    # Analytic accounts
    AnalyticAccount = Model.get('analytic_account.account')
    vars.analytic_root_account = AnalyticAccount(
        name='Root',
        type='root',
        )
    vars.analytic_root_account.save()
    vars.default_analytic_account = AnalyticAccount(
        name='Default',
        type='normal',
        root=vars.analytic_root_account,
        parent=vars.analytic_root_account,
        )
    vars.default_analytic_account.save()
    vars.special_analytic_account = AnalyticAccount(
        name='Special',
        type='normal',
        root=vars.analytic_root_account,
        parent=vars.analytic_root_account,
        )
    vars.special_analytic_account.save()

    PartyConfiguration = Model.get('party.configuration')
    party_config = PartyConfiguration(1)
    party_config.default_receivable_analytic_account = vars.default_analytic_account
    party_config.default_payable_analytic_account = vars.default_analytic_account
    party_config.save()

    # Set analytic accounts to accounts
    Account = Model.get('account.account')
    accounts = Account.find([])
    for account in accounts:
        if account.code.startswith('6') or account.code.startswith('7'):
            account.analytic_required.append(AnalyticAccount(vars.analytic_root_account.id))
        else:
            account.analytic_forbidden.append(AnalyticAccount(vars.analytic_root_account.id))
    Account.save(accounts)

    # Create account category
    ProductCategory = Model.get('product.category')
    vars.account_category = ProductCategory(
        name="Account Category",
        accounting=True,
        account_expense=vars.expense,
        account_revenue=vars.revenue,
        customer_taxes=[vars.customer_vat_10],
        supplier_taxes=[vars.supplier_vat_10],
        )
    vars.account_category.save()

    ProductUom = Model.get('product.uom')
    vars.unit, = ProductUom.find([('name', '=', 'Unit')])

    # Create pricelist
    PriceList = Model.get('product.price_list')
    PriceListLine = Model.get('product.price_list.line')
    line1 = PriceListLine(
        sequence=1,
        formula='list_price',
        )
    vars.pricelist = PriceList(
        name='Pricelist',
        lines=[line1],
        )
    vars.pricelist.save()

    # Create carrier
    ProductTemplate = Model.get('product.template')
    carrier_template = ProductTemplate(
        name='Carrier',
        default_uom=vars.unit,
        type='service',
        account_category=vars.account_category,
        salable=True,
        sale_uom=vars.unit,
        )
    carrier_template.list_price = Decimal('10')
    carrier_template.save()
    carrier_product, = carrier_template.products

    Carrier = Model.get('carrier')
    carrier_party = Party(name='Carrier')
    carrier_party.save()
    carrier = Carrier(
        party=carrier_party,
        carrier_product=carrier_product,
        )
    carrier.selections.new()
    carrier.save()

    # Create parties
    Party = Model.get('party.party')
    vars.customer = Party(
        name='Customer',
        customer=True,
        import_policy='assigned',
        carrier=carrier,
        company_credit_limit=Decimal('10000'),
        sale_price_list=vars.pricelist,
        )
    vars.customer.save()

    vars.special_customer = Party(
        name='Special Customer',
        customer=True,
        credit_limit_amount=Decimal('1000000'),
        sale_price_list=vars.pricelist,
        receivable_analytic_account=vars.special_analytic_account,
        payable_analytic_account=vars.special_analytic_account,
        )
    vars.special_customer.save()

    vars.supplier = Party(
        name='Supplier',
        supplier=True
        )
    vars.supplier.save()

    # Create pending account and another expense account
    Account = Model.get('account.account')
    vars.pending_payable = Account(
        code='PR',
        name='Pending payable',
        type=vars.payable.type,
        reconcile=True
        )
    vars.pending_payable.save()

    # Set Purchase Configuration
    PurchaseConfig = Model.get('purchase.configuration')
    vars.purchase_config = PurchaseConfig(1)
    vars.purchase_config.purchase_invoice_method = 'shipment'
    vars.purchase_config.pending_invoice_account = vars.pending_payable
    vars.purchase_config.supply_period = dt.timedelta(days=30)
    vars.purchase_config.save()

    # Get stock locations
    StockConfiguration = Model.get('stock.configuration')
    vars.stock_config = StockConfiguration(1)
    vars.stock_config.purchase_warehouse = vars.warehouse
    vars.stock_config.save()

    vars.supplier_location, = Location.find([('code', '=', 'SUP')])
    vars.input_location, = Location.find([('code', '=', 'IN')])

    # Create product
    vars.template = ProductTemplate(
        name='Product1',
        default_uom=vars.unit,
        type='goods',
        box_units=6,
        salable=True,
        purchasable=True,
        account_category=vars.account_category,
        vintage_required='required',
        )
    # List price must be set outside the constructor
    vars.template.list_price = Decimal('20')
    vars.template.save()
    vars.product, = vars.template.products

    # Create lot
    Lot = Model.get('stock.lot')
    vars.lot = Lot(
        number='1',
        product=vars.product,
        vintage=2020,
        )
    vars.lot.save()

    # Create stock move for the product with 5 units at unit price 10
    StockMove = Model.get('stock.move')

    # Skipping warning
    stock_move = StockMove(
        product=vars.product,
        from_location=vars.supplier_location,
        to_location=vars.warehouse.storage_location,
        quantity=5,
        currency=vars.company.currency,
        unit_price=Decimal('10'),
        )
    # Skip warning because the move has no origin
    vars.config.skip_warning = True
    stock_move.click('do')
    vars.config.skip_warning = False

    # Create payment term
    vars.payment_term = create_payment_term()
    vars.payment_term.save()

    return vars
