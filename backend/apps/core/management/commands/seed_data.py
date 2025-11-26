from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from decimal import Decimal
from apps.accounts.models import Department, Role
from apps.masterdata.models import Customer, Supplier, Warehouse, Item, ItemCategory
from apps.projects.models import Project, ProjectMember, ProjectTask, ProjectBOM
from apps.purchase.models import PurchaseRequest, PurchaseRequestLine, PurchaseOrder, PurchaseOrderLine
from apps.sales.models import SalesOrder, SalesOrderLine
from apps.inventory.models import Stock, StockMove
from apps.finance.models import Expense, AccountReceivable

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Starting data seeding...')
        
        # Clear existing data (except admin user) - must delete in correct order due to foreign keys
        self.stdout.write('Cleaning existing sample data...')
        AccountReceivable.objects.all().delete()
        Expense.objects.all().delete()
        StockMove.objects.all().delete()
        Stock.objects.all().delete()
        SalesOrder.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        PurchaseRequest.objects.all().delete()
        ProjectBOM.objects.all().delete()
        ProjectTask.objects.all().delete()
        ProjectMember.objects.all().delete()
        Project.objects.all().delete()
        Item.objects.all().delete()
        ItemCategory.objects.all().delete()
        Warehouse.objects.all().delete()
        Supplier.objects.all().delete()
        Customer.objects.all().delete()
        User.objects.exclude(username='admin').delete()
        Role.objects.all().delete()
        Department.objects.all().delete()
        
        # Get admin user
        admin = User.objects.get(username='admin')
        
        # 1. Create Departments
        self.stdout.write('Creating departments...')
        dept_sales = Department.objects.create(name='Sales Department', code='SALES')
        dept_engineering = Department.objects.create(name='Engineering Department', code='ENG')
        dept_procurement = Department.objects.create(name='Procurement Department', code='PROC')
        dept_finance = Department.objects.create(name='Finance Department', code='FIN')
        
        # 2. Create Roles
        self.stdout.write('Creating roles...')
        role_manager = Role.objects.create(
            name='Project Manager',
            code='PM',
            description='Can manage projects and view all data',
            data_scope='ALL'
        )
        role_engineer = Role.objects.create(
            name='Engineer',
            code='ENG',
            description='Can work on assigned tasks',
            data_scope='DEPARTMENT'
        )
        role_buyer = Role.objects.create(
            name='Buyer',
            code='BUYER',
            description='Can create purchase orders',
            data_scope='DEPARTMENT'
        )
        
        # 3. Create Users
        self.stdout.write('Creating users...')
        user_john = User.objects.create_user(
            username='john.smith',
            email='john.smith@example.com',
            password='password123',
            first_name='John',
            last_name='Smith',
            employee_id='EMP001',
            department=dept_engineering,
            role=role_manager,
            is_staff=True
        )
        
        user_sarah = User.objects.create_user(
            username='sarah.johnson',
            email='sarah.johnson@example.com',
            password='password123',
            first_name='Sarah',
            last_name='Johnson',
            employee_id='EMP002',
            department=dept_engineering,
            role=role_engineer
        )
        
        user_mike = User.objects.create_user(
            username='mike.chen',
            email='mike.chen@example.com',
            password='password123',
            first_name='Mike',
            last_name='Chen',
            employee_id='EMP003',
            department=dept_procurement,
            role=role_buyer
        )
        
        # 4. Create Customers
        self.stdout.write('Creating customers...')
        customer1 = Customer.objects.create(
            code='CUST001',
            name='Tech Solutions Inc.',
            contact_person='David Brown',
            phone='+1-555-0101',
            email='david@techsolutions.com',
            address='123 Tech Street, Silicon Valley, CA 94025',
            credit_limit=Decimal('100000.00'),
            status='ACTIVE',
            created_by=admin
        )
        
        customer2 = Customer.objects.create(
            code='CUST002',
            name='Global Manufacturing Corp',
            contact_person='Lisa Wang',
            phone='+1-555-0102',
            email='lisa@globalmanuf.com',
            address='456 Industrial Blvd, Detroit, MI 48201',
            credit_limit=Decimal('200000.00'),
            status='ACTIVE',
            created_by=admin
        )
        
        customer3 = Customer.objects.create(
            code='CUST003',
            name='Smart Devices Ltd',
            contact_person='Robert Taylor',
            phone='+1-555-0103',
            email='robert@smartdevices.com',
            address='789 Innovation Way, Austin, TX 78701',
            credit_limit=Decimal('150000.00'),
            status='ACTIVE',
            created_by=admin
        )
        
        # 5. Create Suppliers
        self.stdout.write('Creating suppliers...')
        supplier1 = Supplier.objects.create(
            code='SUPP001',
            name='Electronic Components Ltd',
            contact_person='Tom Wilson',
            phone='+1-555-0201',
            email='tom@electroniccomp.com',
            address='111 Component Ave, Shenzhen, China',
            payment_terms='Net 30',
            status='ACTIVE',
            created_by=admin
        )
        
        supplier2 = Supplier.objects.create(
            code='SUPP002',
            name='Industrial Parts Supply',
            contact_person='Emma Davis',
            phone='+1-555-0202',
            email='emma@industrialparts.com',
            address='222 Parts Road, Chicago, IL 60601',
            payment_terms='Net 45',
            status='ACTIVE',
            created_by=admin
        )
        
        supplier3 = Supplier.objects.create(
            code='SUPP003',
            name='Quality Materials Inc',
            contact_person='James Lee',
            phone='+1-555-0203',
            email='james@qualitymat.com',
            address='333 Material Street, Houston, TX 77001',
            payment_terms='Net 30',
            status='ACTIVE',
            created_by=admin
        )
        
        # 6. Create Warehouses
        self.stdout.write('Creating warehouses...')
        warehouse_main = Warehouse.objects.create(
            code='WH001',
            name='Main Warehouse',
            location='Building A, Floor 1',
            warehouse_type='main',
            created_by=admin
        )
        
        warehouse_production = Warehouse.objects.create(
            code='WH002',
            name='Production Warehouse',
            location='Building B, Floor 2',
            warehouse_type='main',
            created_by=admin
        )
        
        # 7. Create Item Categories
        self.stdout.write('Creating item categories...')
        cat_electronics = ItemCategory.objects.create(
            name='Electronics',
            code='ELEC',
            created_by=admin
        )
        
        cat_mechanical = ItemCategory.objects.create(
            name='Mechanical Parts',
            code='MECH',
            created_by=admin
        )
        
        cat_materials = ItemCategory.objects.create(
            name='Raw Materials',
            code='MAT',
            created_by=admin
        )
        
        # 8. Create Items
        self.stdout.write('Creating items...')
        item1 = Item.objects.create(
            sku='ITEM-001',
            name='Microcontroller Board',
            specification='ARM Cortex-M4, 32KB RAM',
            unit='PCS',
            category=cat_electronics,
            standard_cost=Decimal('25.50'),
            min_stock=50,
            max_stock=500,
            is_active=True,
            created_by=admin
        )
        
        item2 = Item.objects.create(
            sku='ITEM-002',
            name='LCD Display 7 inch',
            specification='1024x600 resolution, Touch screen',
            unit='PCS',
            category=cat_electronics,
            standard_cost=Decimal('45.00'),
            min_stock=30,
            max_stock=300,
            is_active=True,
            created_by=admin
        )
        
        item3 = Item.objects.create(
            sku='ITEM-003',
            name='Aluminum Enclosure',
            specification='200x150x80mm, Powder coated',
            unit='PCS',
            category=cat_mechanical,
            standard_cost=Decimal('18.75'),
            min_stock=40,
            max_stock=400,
            is_active=True,
            created_by=admin
        )
        
        item4 = Item.objects.create(
            sku='ITEM-004',
            name='Power Supply Module',
            specification='5V 3A, Universal input',
            unit='PCS',
            category=cat_electronics,
            standard_cost=Decimal('12.30'),
            min_stock=60,
            max_stock=600,
            is_active=True,
            created_by=admin
        )
        
        item5 = Item.objects.create(
            sku='ITEM-005',
            name='PCB Board Custom',
            specification='4-layer PCB with components',
            unit='PCS',
            category=cat_electronics,
            standard_cost=Decimal('35.00'),
            min_stock=20,
            max_stock=200,
            is_active=True,
            created_by=admin
        )
        
        item6 = Item.objects.create(
            sku='ITEM-006',
            name='Cable Assembly',
            specification='Custom length with connectors',
            unit='PCS',
            category=cat_electronics,
            standard_cost=Decimal('8.50'),
            min_stock=100,
            max_stock=1000,
            is_active=True,
            created_by=admin
        )
        
        # 9. Create Initial Stock
        self.stdout.write('Creating initial stock...')
        for item in [item1, item2, item3, item4, item5, item6]:
            stock = Stock.objects.create(
                warehouse=warehouse_main,
                item=item,
                qty_on_hand=100,
                qty_reserved=0
            )
            
            # Create stock move for initial stock
            StockMove.objects.create(
                move_no=f'INIT-{item.sku}',
                item=item,
                warehouse_to=warehouse_main,
                qty=100,
                unit_cost=item.standard_cost,
                move_type='ADJUSTMENT',
                reference_type='initial_stock',
                reference_id=stock.id,
                move_date=timezone.now() - timedelta(days=30),
                status='COMPLETED',
                created_by=admin
            )
        
        # 10. Create Projects
        self.stdout.write('Creating projects...')
        project1 = Project.objects.create(
            code='PRJ-2025-001',
            name='Smart Home Control System',
            customer=customer1,
            manager=user_john,
            start_date=timezone.now().date() - timedelta(days=60),
            end_date=timezone.now().date() + timedelta(days=90),
            status='ACTIVE',
            budget_total=Decimal('150000.00'),
            budget_material=Decimal('80000.00'),
            budget_labor=Decimal('50000.00'),
            budget_expense=Decimal('20000.00'),
            created_by=admin
        )
        
        project2 = Project.objects.create(
            code='PRJ-2025-002',
            name='Industrial IoT Gateway',
            customer=customer2,
            manager=user_john,
            start_date=timezone.now().date() - timedelta(days=45),
            end_date=timezone.now().date() + timedelta(days=105),
            status='ACTIVE',
            budget_total=Decimal('200000.00'),
            budget_material=Decimal('120000.00'),
            budget_labor=Decimal('60000.00'),
            budget_expense=Decimal('20000.00'),
            created_by=admin
        )
        
        project3 = Project.objects.create(
            code='PRJ-2025-003',
            name='Portable Display Unit',
            customer=customer3,
            manager=user_john,
            start_date=timezone.now().date() - timedelta(days=20),
            end_date=timezone.now().date() + timedelta(days=130),
            status='ACTIVE',
            budget_total=Decimal('100000.00'),
            budget_material=Decimal('55000.00'),
            budget_labor=Decimal('35000.00'),
            budget_expense=Decimal('10000.00'),
            created_by=admin
        )
        
        # 11. Create Project Members
        self.stdout.write('Creating project members...')
        ProjectMember.objects.create(
            project=project1,
            user=user_john,
            role='Project Manager',
            hourly_rate=Decimal('85.00'),
            created_by=admin
        )
        
        ProjectMember.objects.create(
            project=project1,
            user=user_sarah,
            role='Senior Engineer',
            hourly_rate=Decimal('65.00'),
            created_by=admin
        )
        
        ProjectMember.objects.create(
            project=project2,
            user=user_john,
            role='Project Manager',
            hourly_rate=Decimal('85.00'),
            created_by=admin
        )
        
        ProjectMember.objects.create(
            project=project2,
            user=user_sarah,
            role='Lead Engineer',
            hourly_rate=Decimal('70.00'),
            created_by=admin
        )
        
        # 12. Create Project Tasks
        self.stdout.write('Creating project tasks...')
        task1 = ProjectTask.objects.create(
            project=project1,
            code='TASK-001',
            name='Hardware Design',
            assignee=user_sarah,
            planned_hours=120,
            actual_hours=85,
            progress_percent=70,
            status='IN_PROGRESS',
            created_by=admin
        )
        
        task2 = ProjectTask.objects.create(
            project=project1,
            code='TASK-002',
            name='Software Development',
            assignee=user_sarah,
            planned_hours=160,
            actual_hours=40,
            progress_percent=25,
            status='IN_PROGRESS',
            created_by=admin
        )
        
        task3 = ProjectTask.objects.create(
            project=project1,
            code='TASK-003',
            name='Testing & QA',
            assignee=user_john,
            planned_hours=80,
            actual_hours=0,
            progress_percent=0,
            status='TODO',
            created_by=admin
        )
        
        task4 = ProjectTask.objects.create(
            project=project2,
            code='TASK-001',
            name='System Architecture',
            assignee=user_john,
            planned_hours=100,
            actual_hours=95,
            progress_percent=95,
            status='IN_PROGRESS',
            created_by=admin
        )
        
        task5 = ProjectTask.objects.create(
            project=project2,
            code='TASK-002',
            name='Prototype Development',
            assignee=user_sarah,
            planned_hours=200,
            actual_hours=120,
            progress_percent=60,
            status='IN_PROGRESS',
            created_by=admin
        )
        
        # 13. Create Project BOM
        self.stdout.write('Creating project BOMs...')
        ProjectBOM.objects.create(
            project=project1,
            item=item1,
            planned_qty=50,
            actual_qty=30,
            created_by=admin
        )
        
        ProjectBOM.objects.create(
            project=project1,
            item=item2,
            planned_qty=50,
            actual_qty=25,
            created_by=admin
        )
        
        ProjectBOM.objects.create(
            project=project1,
            item=item3,
            planned_qty=50,
            actual_qty=20,
            created_by=admin
        )
        
        ProjectBOM.objects.create(
            project=project2,
            item=item1,
            planned_qty=100,
            actual_qty=50,
            created_by=admin
        )
        
        ProjectBOM.objects.create(
            project=project2,
            item=item4,
            planned_qty=100,
            actual_qty=40,
            created_by=admin
        )
        
        # 14. Create Purchase Requests
        self.stdout.write('Creating purchase requests...')
        pr1 = PurchaseRequest.objects.create(
            request_no='PR-2025-001',
            project=project1,
            requestor=user_mike,
            required_date=timezone.now().date() + timedelta(days=30),
            status='APPROVED',
            total_amount=Decimal('5000.00'),
            created_by=user_mike
        )
        
        PurchaseRequestLine.objects.create(
            pr=pr1,
            item=item1,
            qty=100,
            estimated_price=Decimal('25.00'),
            project=project1,
            created_by=user_mike
        )
        
        PurchaseRequestLine.objects.create(
            pr=pr1,
            item=item2,
            qty=50,
            estimated_price=Decimal('45.00'),
            project=project1,
            created_by=user_mike
        )
        
        # 15. Create Purchase Orders
        self.stdout.write('Creating purchase orders...')
        po1 = PurchaseOrder.objects.create(
            order_no='PO-2025-001',
            supplier=supplier1,
            project=project1,
            delivery_date=timezone.now().date() + timedelta(days=15),
            status='CONFIRMED',
            total_amount=Decimal('4750.00'),
            payment_terms='Net 30',
            created_by=user_mike
        )
        
        PurchaseOrderLine.objects.create(
            po=po1,
            item=item1,
            qty=100,
            unit_price=Decimal('25.00'),
            received_qty=100,
            created_by=user_mike
        )
        
        PurchaseOrderLine.objects.create(
            po=po1,
            item=item2,
            qty=50,
            unit_price=Decimal('44.50'),
            received_qty=50,
            created_by=user_mike
        )
        
        # 16. Create Sales Orders
        self.stdout.write('Creating sales orders...')
        so1 = SalesOrder.objects.create(
            order_no='SO-2025-001',
            customer=customer1,
            project=project1,
            order_date=timezone.now().date() - timedelta(days=50),
            delivery_date=timezone.now().date() + timedelta(days=40),
            status='CONFIRMED',
            total_amount=Decimal('150000.00'),
            created_by=admin
        )
        
        SalesOrderLine.objects.create(
            so=so1,
            item=item1,
            qty=50,
            unit_price=Decimal('3000.00'),
            delivered_qty=30,
            created_by=admin
        )
        
        so2 = SalesOrder.objects.create(
            order_no='SO-2025-002',
            customer=customer2,
            project=project2,
            order_date=timezone.now().date() - timedelta(days=40),
            delivery_date=timezone.now().date() + timedelta(days=60),
            status='CONFIRMED',
            total_amount=Decimal('200000.00'),
            created_by=admin
        )
        
        SalesOrderLine.objects.create(
            so=so2,
            item=item1,
            qty=100,
            unit_price=Decimal('2000.00'),
            delivered_qty=50,
            created_by=admin
        )
        
        # 17. Create Stock Moves for Project Consumption
        self.stdout.write('Creating stock moves for project consumption...')
        
        # Project 1 material consumption
        move1 = StockMove.objects.create(
            move_no='CONS-PRJ1-001',
            item=item1,
            warehouse_from=warehouse_main,
            qty=30,
            unit_cost=Decimal('25.50'),
            move_type='OUT_PROJECT',
            reference_type='project',
            reference_id=project1.id,
            project=project1,
            move_date=timezone.now() - timedelta(days=10),
            status='COMPLETED',
            created_by=admin
        )
        
        move2 = StockMove.objects.create(
            move_no='CONS-PRJ1-002',
            item=item2,
            warehouse_from=warehouse_main,
            qty=25,
            unit_cost=Decimal('45.00'),
            move_type='OUT_PROJECT',
            reference_type='project',
            reference_id=project1.id,
            project=project1,
            move_date=timezone.now() - timedelta(days=8),
            status='COMPLETED',
            created_by=admin
        )
        
        move3 = StockMove.objects.create(
            move_no='CONS-PRJ1-003',
            item=item3,
            warehouse_from=warehouse_main,
            qty=20,
            unit_cost=Decimal('18.75'),
            move_type='OUT_PROJECT',
            reference_type='project',
            reference_id=project1.id,
            project=project1,
            move_date=timezone.now() - timedelta(days=5),
            status='COMPLETED',
            created_by=admin
        )
        
        # Project 2 material consumption
        move4 = StockMove.objects.create(
            move_no='CONS-PRJ2-001',
            item=item1,
            warehouse_from=warehouse_main,
            qty=50,
            unit_cost=Decimal('25.50'),
            move_type='OUT_PROJECT',
            reference_type='project',
            reference_id=project2.id,
            project=project2,
            move_date=timezone.now() - timedelta(days=12),
            status='COMPLETED',
            created_by=admin
        )
        
        move5 = StockMove.objects.create(
            move_no='CONS-PRJ2-002',
            item=item4,
            warehouse_from=warehouse_main,
            qty=40,
            unit_cost=Decimal('12.30'),
            move_type='OUT_PROJECT',
            reference_type='project',
            reference_id=project2.id,
            project=project2,
            move_date=timezone.now() - timedelta(days=7),
            status='COMPLETED',
            created_by=admin
        )
        
        # Update stock quantities
        for item in [item1, item2, item3, item4]:
            stock = Stock.objects.filter(warehouse=warehouse_main, item=item).first()
            if stock:
                consumed = StockMove.objects.filter(
                    item=item,
                    warehouse_from=warehouse_main,
                    move_type='OUT_PROJECT',
                    status='completed'
                ).aggregate(total=Sum('qty'))['total'] or 0
                
                stock.qty_on_hand = 100 - consumed
                stock.save()
        
        # 18. Create Expenses
        self.stdout.write('Creating expenses...')
        Expense.objects.create(
            expense_no='EXP-2025-001',
            project=project1,
            user=user_john,
            expense_date=timezone.now().date() - timedelta(days=20),
            category='TRAVEL',
            amount=Decimal('1250.50'),
            description='Client meeting travel expenses',
            status='APPROVED',
            created_by=user_john
        )
        
        Expense.objects.create(
            expense_no='EXP-2025-002',
            project=project1,
            user=user_sarah,
            expense_date=timezone.now().date() - timedelta(days=15),
            category='OTHER',
            amount=Decimal('850.00'),
            description='Test equipment purchase',
            status='APPROVED',
            created_by=user_sarah
        )
        
        Expense.objects.create(
            expense_no='EXP-2025-003',
            project=project2,
            user=user_john,
            expense_date=timezone.now().date() - timedelta(days=10),
            category='TRAVEL',
            amount=Decimal('2100.00'),
            description='Factory visit and inspection',
            status='APPROVED',
            created_by=user_john
        )
        
        Expense.objects.create(
            expense_no='EXP-2025-004',
            project=project2,
            user=user_sarah,
            expense_date=timezone.now().date() - timedelta(days=5),
            category='OFFICE',
            amount=Decimal('450.00'),
            description='Development supplies',
            status='APPROVED',
            created_by=user_sarah
        )
        
        # 19. Create Accounts Receivable
        self.stdout.write('Creating accounts receivable...')
        AccountReceivable.objects.create(
            ar_no='AR-2025-001',
            customer=customer1,
            so=so1,
            project=project1,
            invoice_no='INV-2025-001',
            invoice_date=timezone.now().date() - timedelta(days=45),
            amount_due=Decimal('150000.00'),
            amount_paid=Decimal('75000.00'),
            due_date=timezone.now().date() + timedelta(days=15),
            status='PARTIAL',
            created_by=admin
        )
        
        AccountReceivable.objects.create(
            ar_no='AR-2025-002',
            customer=customer2,
            so=so2,
            project=project2,
            invoice_no='INV-2025-002',
            invoice_date=timezone.now().date() - timedelta(days=35),
            amount_due=Decimal('200000.00'),
            amount_paid=Decimal('0.00'),
            due_date=timezone.now().date() + timedelta(days=25),
            status='PENDING',
            created_by=admin
        )
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded database with sample data!'))
        self.stdout.write(self.style.SUCCESS('\n=== Sample Data Summary ==='))
        self.stdout.write(f'Departments: {Department.objects.count()}')
        self.stdout.write(f'Roles: {Role.objects.count()}')
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Customers: {Customer.objects.count()}')
        self.stdout.write(f'Suppliers: {Supplier.objects.count()}')
        self.stdout.write(f'Warehouses: {Warehouse.objects.count()}')
        self.stdout.write(f'Items: {Item.objects.count()}')
        self.stdout.write(f'Projects: {Project.objects.count()}')
        self.stdout.write(f'Project Tasks: {ProjectTask.objects.count()}')
        self.stdout.write(f'Purchase Orders: {PurchaseOrder.objects.count()}')
        self.stdout.write(f'Sales Orders: {SalesOrder.objects.count()}')
        self.stdout.write(f'Stock Moves: {StockMove.objects.count()}')
        self.stdout.write(f'Expenses: {Expense.objects.count()}')
        self.stdout.write(self.style.SUCCESS('\n=== Login Credentials ==='))
        self.stdout.write('Admin: admin / admin123')
        self.stdout.write('Manager: john.smith / password123')
        self.stdout.write('Engineer: sarah.johnson / password123')
        self.stdout.write('Buyer: mike.chen / password123')

