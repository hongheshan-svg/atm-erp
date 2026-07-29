"""
物料编码生成器
根据业务规则生成物料编码：一级代码(1位) + 二级代码(1位) + 年份(2位) + 三级流水号(6位)
"""

from datetime import datetime

from django.db.models import Max


class ItemCodeGenerator:
    """
    物料编码生成器

    编码规则：
    - 一级代码(1位): 1=有图, 2=无图
    - 二级代码(1位): 1=机加, 2=钣金, 3=特殊工艺, 4=其他, 5=机械类, 6=电气类, 7=耗材辅料, 8=办公用品
    - 年份(2位): 有图=当前年份后两位, 无图=99
    - 三级流水号(6位): 根据年份循环累加，000001-999999
    """

    # 一级代码定义
    LEVEL1_HAS_DRAWING = '1'  # 有图
    LEVEL1_NO_DRAWING = '2'  # 无图

    # 二级代码定义
    LEVEL2_CHOICES = {
        '1': '机加',
        '2': '钣金',
        '3': '特殊工艺',
        '4': '其他',
        '5': '机械类',
        '6': '电气类',
        '7': '耗材辅料',
        '8': '办公用品',
    }

    @classmethod
    def generate_code(cls, level1_code, level2_code):
        """
        生成物料编码

        Args:
            level1_code: 一级代码 ('1'=有图, '2'=无图)
            level2_code: 二级代码 ('1'-'8')

        Returns:
            生成的物料编码，格式：如 1125000001
        """
        # 验证输入
        if level1_code not in [cls.LEVEL1_HAS_DRAWING, cls.LEVEL1_NO_DRAWING]:
            raise ValueError(f"一级代码必须是 '1'(有图) 或 '2'(无图)，当前值：{level1_code}")

        if level2_code not in cls.LEVEL2_CHOICES:
            raise ValueError(f"二级代码必须是 '1'-'8' 之一，当前值：{level2_code}")

        # 确定年份
        if level1_code == cls.LEVEL1_HAS_DRAWING:
            # 有图：使用当前年份后两位
            year_code = datetime.now().strftime('%y')
        else:
            # 无图：固定为99
            year_code = '99'

        # 获取下一个流水号（基于年份前缀）
        prefix = f'{level1_code}{level2_code}{year_code}'
        next_seq = cls._get_next_sequence(prefix)

        # 生成完整编码
        code = f'{prefix}{next_seq:06d}'

        return code

    @classmethod
    def _get_next_sequence(cls, prefix):
        """
        获取指定前缀的下一个未被占用的流水号。

        注意：取号本身不预占编码，跨请求并发仍可能取到同一号，
        由调用方在插入撞唯一约束时重新取号（见 ItemViewSet.import_excel）。

        Args:
            prefix: 编码前缀（一级代码+二级代码+年份），如 '1125'

        Returns:
            下一个流水号（1-999999）
        """
        from apps.masterdata.models import Item

        # 必须用 all_objects：Item.sku 是全表唯一约束，软删除的行仍占着编码，
        # 原先按 is_deleted=False 取最大值会把已软删除的号重新发出去，插入必撞唯一约束。
        #
        # 原实现的 `.select_for_update().aggregate(Max(...))` 起不到并发保护：
        # 行锁只能锁住已存在的行，锁不住「即将插入的下一号」；且取号事务在调用方
        # 真正 create 之前就已提交、锁早已释放。因此这里改为「跳过已被占用的号」，
        # 并要求调用方在 create 撞 IntegrityError 时重新取号（见 ItemViewSet.import_excel）。
        max_code = Item.all_objects.filter(sku__startswith=prefix).aggregate(max_code=Max('sku'))['max_code']

        if max_code and len(max_code) >= len(prefix) + 6:
            # 提取流水号部分
            try:
                current_seq = int(max_code[len(prefix) : len(prefix) + 6])
                next_seq = current_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        # 历史数据里可能存在编码格式不规整的行，导致 Max 取到的并非真正最大号，
        # 逐个跳过已占用的流水号，避免直接发出一个必然冲突的编码。
        taken = set(Item.all_objects.filter(sku__startswith=prefix).values_list('sku', flat=True))
        while next_seq <= 999999 and f'{prefix}{next_seq:06d}' in taken:
            next_seq += 1

        # 检查是否超过最大值
        if next_seq > 999999:
            raise ValueError(f'编码前缀 {prefix} 的流水号已达到最大值 999999')

        return next_seq

    @classmethod
    def parse_code(cls, code):
        """
        解析物料编码

        Args:
            code: 物料编码

        Returns:
            dict: 包含各部分信息的字典
        """
        if not code or len(code) < 10:
            return {'valid': False, 'error': '编码长度不正确'}

        try:
            level1_code = code[0]
            level2_code = code[1]
            year_code = code[2:4]
            sequence = code[4:10]

            return {
                'valid': True,
                'level1_code': level1_code,
                'level1_name': '有图' if level1_code == '1' else '无图' if level1_code == '2' else '未知',
                'level2_code': level2_code,
                'level2_name': cls.LEVEL2_CHOICES.get(level2_code, '未知'),
                'year_code': year_code,
                'sequence': sequence,
                'full_code': code,
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    @classmethod
    def get_level2_choices(cls):
        """获取二级代码选项列表"""
        return [{'value': k, 'label': f'{k}-{v}'} for k, v in cls.LEVEL2_CHOICES.items()]

    @classmethod
    def validate_code_format(cls, code):
        """
        验证编码格式是否正确

        Args:
            code: 物料编码

        Returns:
            tuple: (is_valid, error_message)
        """
        if not code:
            return False, '编码不能为空'

        if len(code) != 10:
            return False, f'编码长度必须为10位，当前长度：{len(code)}'

        if not code.isdigit():
            return False, '编码必须全部为数字'

        level1_code = code[0]
        if level1_code not in ['1', '2']:
            return False, f'一级代码必须是1或2，当前值：{level1_code}'

        level2_code = code[1]
        if level2_code not in cls.LEVEL2_CHOICES:
            return False, f'二级代码必须是1-8，当前值：{level2_code}'

        return True, ''
