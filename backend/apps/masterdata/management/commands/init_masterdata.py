"""
初始化主数据
创建示例物料、客户、供应商、仓库
"""

from django.core.management.base import BaseCommand

from apps.masterdata.models import Customer, Item, ItemCategory, Supplier, Warehouse


class Command(BaseCommand):
    help = '初始化主数据（物料、客户、供应商、仓库）'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始初始化主数据...'))

        # 1. 创建物料分类
        self.stdout.write('创建物料分类...')
        categories = [
            {'name': '原材料', 'code': 'RAW', 'description': '生产用原材料'},
            {'name': '半成品', 'code': 'SEMI', 'description': '半成品'},
            {'name': '成品', 'code': 'FINISHED', 'description': '最终成品'},
            {'name': '辅料', 'code': 'AUX', 'description': '辅助材料'},
            {'name': '办公用品', 'code': 'OFFICE', 'description': '办公用品'},
        ]

        cat_objs = {}
        for cat_data in categories:
            cat, created = ItemCategory.objects.get_or_create(
                code=cat_data['code'], defaults={'name': cat_data['name'], 'description': cat_data['description']}
            )
            cat_objs[cat_data['code']] = cat
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建分类: {cat.name}'))
            else:
                self.stdout.write(f'  - 分类已存在: {cat.name}')

        # 2. 创建物料
        self.stdout.write('创建物料...')
        items = [
            {
                'sku': 'MAT-001',
                'name': '钢板 Q235',
                'specification': '1000x2000x5mm',
                'unit': '张',
                'category': 'RAW',
                'standard_cost': 150.00,
            },
            {
                'sku': 'MAT-002',
                'name': '铝型材',
                'specification': '6060 50x50mm',
                'unit': '米',
                'category': 'RAW',
                'standard_cost': 35.00,
            },
            {
                'sku': 'PROD-001',
                'name': '机箱外壳',
                'specification': '标准款',
                'unit': '件',
                'category': 'SEMI',
                'standard_cost': 280.00,
            },
            {
                'sku': 'PROD-002',
                'name': '控制面板',
                'specification': '7寸触摸屏',
                'unit': '件',
                'category': 'FINISHED',
                'standard_cost': 850.00,
            },
            {
                'sku': 'AUX-001',
                'name': '螺丝 M5x20',
                'specification': '304不锈钢',
                'unit': '个',
                'category': 'AUX',
                'standard_cost': 0.15,
            },
        ]

        for item_data in items:
            item, created = Item.objects.get_or_create(
                sku=item_data['sku'],
                defaults={
                    'name': item_data['name'],
                    'specification': item_data['specification'],
                    'unit': item_data['unit'],
                    'category': cat_objs[item_data['category']],
                    'standard_cost': item_data['standard_cost'],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建物料: {item.sku} - {item.name}'))
            else:
                self.stdout.write(f'  - 物料已存在: {item.sku}')

        # 3. 创建客户
        self.stdout.write('创建客户...')
        customers = [
            {
                'code': 'CUST-001',
                'name': '北京科技有限公司',
                'contact_person': '张经理',
                'phone': '010-12345678',
                'email': 'zhang@bjtech.com',
                'address': '北京市朝阳区科技园',
                'credit_limit': 100000.00,
            },
            {
                'code': 'CUST-002',
                'name': '上海工业集团',
                'contact_person': '李总',
                'phone': '021-87654321',
                'email': 'li@shgroup.com',
                'address': '上海市浦东新区工业路',
                'credit_limit': 500000.00,
            },
            {
                'code': 'CUST-003',
                'name': '深圳电子科技',
                'contact_person': '王工',
                'phone': '0755-11112222',
                'email': 'wang@sztech.com',
                'address': '深圳市南山区科技园',
                'credit_limit': 200000.00,
            },
        ]

        for cust_data in customers:
            cust, created = Customer.objects.get_or_create(
                code=cust_data['code'],
                defaults={
                    'name': cust_data['name'],
                    'contact_person': cust_data['contact_person'],
                    'phone': cust_data['phone'],
                    'email': cust_data['email'],
                    'address': cust_data['address'],
                    'credit_limit': cust_data['credit_limit'],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建客户: {cust.code} - {cust.name}'))
            else:
                self.stdout.write(f'  - 客户已存在: {cust.code}')

        # 4. 创建供应商
        self.stdout.write('创建供应商...')
        suppliers = [
            {
                'code': 'SUP-001',
                'name': '宝钢集团',
                'contact_person': '刘经理',
                'phone': '021-55556666',
                'email': 'liu@baosteel.com',
                'address': '上海市宝山区钢铁大道',
                'payment_terms': '月结30天',
            },
            {
                'code': 'SUP-002',
                'name': '广东铝业',
                'contact_person': '陈总',
                'phone': '020-33334444',
                'email': 'chen@gdalum.com',
                'address': '广州市番禺区工业区',
                'payment_terms': '款到发货',
            },
            {
                'code': 'SUP-003',
                'name': '深圳电子元件',
                'contact_person': '赵工',
                'phone': '0755-77778888',
                'email': 'zhao@szelec.com',
                'address': '深圳市龙岗区电子城',
                'payment_terms': '月结60天',
            },
        ]

        for sup_data in suppliers:
            sup, created = Supplier.objects.get_or_create(
                code=sup_data['code'],
                defaults={
                    'name': sup_data['name'],
                    'contact_person': sup_data['contact_person'],
                    'phone': sup_data['phone'],
                    'email': sup_data['email'],
                    'address': sup_data['address'],
                    'payment_terms': sup_data['payment_terms'],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建供应商: {sup.code} - {sup.name}'))
            else:
                self.stdout.write(f'  - 供应商已存在: {sup.code}')

        # 5. 创建仓库
        self.stdout.write('创建仓库...')
        warehouses = [
            {
                'code': 'WH-01',
                'name': '原材料仓库',
                'location': 'A区1号',
                'warehouse_type': 'MAIN',
                'notes': '存放原材料',
            },
            {'code': 'WH-02', 'name': '成品仓库', 'location': 'B区2号', 'warehouse_type': 'MAIN', 'notes': '存放成品'},
            {
                'code': 'WH-03',
                'name': '半成品仓库',
                'location': 'A区3号',
                'warehouse_type': 'BRANCH',
                'notes': '存放半成品',
            },
        ]

        for wh_data in warehouses:
            wh, created = Warehouse.objects.get_or_create(
                code=wh_data['code'],
                defaults={
                    'name': wh_data['name'],
                    'location': wh_data['location'],
                    'warehouse_type': wh_data['warehouse_type'],
                    'notes': wh_data['notes'],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建仓库: {wh.code} - {wh.name}'))
            else:
                self.stdout.write(f'  - 仓库已存在: {wh.code}')

        self.stdout.write(self.style.SUCCESS('\n主数据初始化完成！'))
