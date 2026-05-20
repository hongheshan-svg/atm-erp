"""
报价比价分析服务
Quotation Comparison Service

针对非标自动化行业增强:
- 智能权重配置（根据物料类型/项目阶段自动调整）
- 多维度推荐算法（价格/综合/交期/质量最优）
- 关键件交期预警和风险评估
- 供应商能力评估集成
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from .rfq_models import RFQ, ItemPriceHistory, QuotationComparison, QuotationScore, SupplierQuotation

logger = logging.getLogger(__name__)


# 权重模板配置（非标自动化行业优化）
WEIGHT_TEMPLATES = {
    'STANDARD': {'price': 40, 'quality': 25, 'delivery': 20, 'service': 15, 'technical': 0},
    'QUALITY_FIRST': {'price': 25, 'quality': 40, 'delivery': 15, 'service': 10, 'technical': 10},
    'DELIVERY_FIRST': {'price': 25, 'quality': 20, 'delivery': 40, 'service': 15, 'technical': 0},
    'PRICE_FIRST': {'price': 55, 'quality': 20, 'delivery': 15, 'service': 10, 'technical': 0},
    'CRITICAL_PART': {'price': 20, 'quality': 35, 'delivery': 25, 'service': 10, 'technical': 10},  # 关键件
    'LONG_LEAD': {'price': 30, 'quality': 20, 'delivery': 35, 'service': 15, 'technical': 0},  # 长周期件
    'CUSTOM_MACHINED': {'price': 30, 'quality': 30, 'delivery': 20, 'service': 10, 'technical': 10},  # 机加件
}

# 风险阈值配置
RISK_THRESHOLDS = {
    'delivery_delay_days': 7,  # 交期超过需求日期超过7天为风险
    'price_increase_rate': 20,  # 涨价超过20%为风险
    'min_reliability_score': 70,  # 可靠性得分低于70为风险
}


class QuotationComparisonService:
    """报价比价分析服务"""

    @classmethod
    def create_comparison(cls, rfq_id, user, weights=None, comparison_type='NORMAL', weight_template='STANDARD'):
        """
        创建比价分析（非标自动化增强版）
        
        Args:
            rfq_id: 询价单ID
            user: 创建用户
            weights: 可选的权重配置 {'price': 40, 'quality': 25, 'delivery': 20, 'service': 15, 'technical': 0}
            comparison_type: 比价类型 NORMAL/SAMPLE/BATCH/URGENT/CHANGE
            weight_template: 权重模板 STANDARD/QUALITY_FIRST/DELIVERY_FIRST/PRICE_FIRST/CUSTOM
        
        Returns:
            QuotationComparison instance
        """
        rfq = RFQ.objects.get(id=rfq_id)

        # 检查是否有有效的报价（SUBMITTED或ACCEPTED状态）
        quotations = SupplierQuotation.objects.filter(
            rfq_supplier__rfq=rfq,
            status__in=['SUBMITTED', 'ACCEPTED'],
            is_deleted=False
        )

        if quotations.count() < 2:
            raise ValueError("至少需要2个供应商报价才能进行比价分析")

        with transaction.atomic():
            # 如果使用模板，获取模板权重
            if weight_template != 'CUSTOM' and not weights:
                weights = WEIGHT_TEMPLATES.get(weight_template, WEIGHT_TEMPLATES['STANDARD'])

            # 分析关键件和长周期件数量
            critical_count, long_lead_count = cls._analyze_critical_items(rfq)

            # 智能调整权重（如果未指定）
            if not weights and (critical_count > 0 or long_lead_count > 0):
                weights = cls._get_smart_weights(rfq, critical_count, long_lead_count)
                weight_template = 'CUSTOM'

            weights = weights or WEIGHT_TEMPLATES['STANDARD']

            # 创建比价分析
            comparison_data = {
                'rfq': rfq,
                'created_by': user,
                'status': 'IN_PROGRESS',
                'comparison_type': comparison_type,
                'weight_template': weight_template,
                'critical_items_count': critical_count,
                'long_lead_items_count': long_lead_count,
                'weight_price': weights.get('price', 40),
                'weight_quality': weights.get('quality', 25),
                'weight_delivery': weights.get('delivery', 20),
                'weight_service': weights.get('service', 15),
                'weight_technical': weights.get('technical', 0),
            }

            comparison = QuotationComparison.objects.create(**comparison_data)

            # 为每个报价创建评分记录
            for quotation in quotations:
                QuotationScore.objects.create(
                    comparison=comparison,
                    quotation=quotation,
                    created_by=user
                )

            # 计算价格统计
            cls._calculate_price_stats(comparison)

            # 自动评分（包含新增维度）
            cls.auto_score(comparison)

            # 风险评估
            cls._assess_risks(comparison)

            logger.info(f"Created comparison {comparison.comparison_no} for RFQ {rfq.rfq_no}")

        return comparison

    @classmethod
    def _analyze_critical_items(cls, rfq):
        """分析询价单中的关键件和长周期件数量"""
        critical_count = 0
        long_lead_count = 0

        # 检查是否有关联项目BOM
        if rfq.project:
            from apps.projects.models import ProjectBOM

            for rfq_line in rfq.lines.filter(is_deleted=False):
                bom_item = ProjectBOM.objects.filter(
                    project=rfq.project,
                    item=rfq_line.item,
                    is_deleted=False
                ).first()

                if bom_item:
                    if bom_item.is_critical:
                        critical_count += 1
                    if bom_item.is_long_lead:
                        long_lead_count += 1

        return critical_count, long_lead_count

    @classmethod
    def _get_smart_weights(cls, rfq, critical_count, long_lead_count):
        """根据物料特性智能计算权重"""
        total_items = rfq.lines.filter(is_deleted=False).count()

        if total_items == 0:
            return WEIGHT_TEMPLATES['STANDARD']

        critical_ratio = critical_count / total_items
        long_lead_ratio = long_lead_count / total_items

        # 关键件占比超过30%，使用关键件权重模板
        if critical_ratio > 0.3:
            return WEIGHT_TEMPLATES['CRITICAL_PART']

        # 长周期件占比超过30%，使用交期优先模板
        if long_lead_ratio > 0.3:
            return WEIGHT_TEMPLATES['LONG_LEAD']

        # 混合情况，动态调整
        base = WEIGHT_TEMPLATES['STANDARD'].copy()

        # 有关键件时增加质量权重
        if critical_count > 0:
            quality_boost = min(10, critical_ratio * 20)
            base['quality'] += quality_boost
            base['price'] -= quality_boost / 2
            base['service'] -= quality_boost / 2

        # 有长周期件时增加交期权重
        if long_lead_count > 0:
            delivery_boost = min(10, long_lead_ratio * 20)
            base['delivery'] += delivery_boost
            base['price'] -= delivery_boost

        return base

    @classmethod
    def _calculate_price_stats(cls, comparison):
        """计算价格统计"""
        prices = list(
            comparison.scores.values_list('quotation__total_amount', flat=True)
        )

        if prices:
            comparison.min_price = min(prices)
            comparison.max_price = max(prices)
            comparison.avg_price = sum(prices) / len(prices)
            comparison.save()

    @classmethod
    def auto_score(cls, comparison):
        """自动评分（所有维度）"""
        cls.auto_score_price(comparison)
        cls.auto_score_delivery(comparison)
        cls.auto_score_technical(comparison)
        cls.auto_score_reliability(comparison)
        cls.calculate_total_scores(comparison)
        cls.calculate_multi_dimension_ranks(comparison)

    @classmethod
    def auto_score_price(cls, comparison):
        """
        自动计算价格得分
        算法: 最低价得100分，其他按比例递减
        """
        scores = comparison.scores.select_related('quotation').all()

        if not scores:
            return

        prices = [(s, float(s.quotation.total_amount)) for s in scores]
        min_price = min(p[1] for p in prices) if prices else 0

        for score, price in prices:
            if min_price > 0 and price > 0:
                # 价格得分 = (最低价 / 当前价) * 100
                score.score_price = Decimal(str(min_price / price * 100))
            else:
                score.score_price = Decimal('0')
            score.save()

        logger.info(f"Auto scored prices for comparison {comparison.comparison_no}")

    @classmethod
    def auto_score_delivery(cls, comparison):
        """
        自动计算交期得分
        算法: 最短交期得100分，其他按比例递减
        """
        scores = comparison.scores.select_related('quotation').all()

        if not scores:
            return

        lead_times = []
        for score in scores:
            avg_lead_time = score.quotation.lines.aggregate(
                avg=Avg('lead_time_days')
            )['avg'] or 999
            lead_times.append((score, float(avg_lead_time)))

        min_lead_time = min(lt[1] for lt in lead_times) if lead_times else 0

        for score, lead_time in lead_times:
            if min_lead_time > 0 and lead_time > 0:
                score.score_delivery = Decimal(str(min_lead_time / lead_time * 100))
            else:
                score.score_delivery = Decimal('0')
            score.save()

        logger.info(f"Auto scored delivery for comparison {comparison.comparison_no}")

    @classmethod
    def auto_score_technical(cls, comparison):
        """
        自动计算技术能力得分（基于供应商评价数据）
        """
        scores = comparison.scores.select_related('quotation__rfq_supplier__supplier').all()

        if not scores:
            return

        for score in scores:
            supplier = score.quotation.rfq_supplier.supplier

            # 从供应商评价中获取技术能力得分
            try:
                from apps.purchase.evaluation_models import SupplierEvaluation

                # 获取最近的评价
                latest_eval = SupplierEvaluation.objects.filter(
                    supplier=supplier,
                    is_deleted=False
                ).order_by('-evaluation_date').first()

                if latest_eval:
                    # 假设评价中有技术能力指标
                    technical_scores = latest_eval.scores.filter(
                        indicator__category='TECHNICAL'
                    ).values_list('score', flat=True)

                    if technical_scores:
                        avg_technical = sum(technical_scores) / len(technical_scores)
                        score.score_technical = Decimal(str(avg_technical))
                    else:
                        score.score_technical = Decimal('75')  # 默认中等
                else:
                    score.score_technical = Decimal('75')  # 无评价默认中等

            except Exception as e:
                logger.warning(f"Failed to get technical score for supplier {supplier.id}: {e}")
                score.score_technical = Decimal('75')

            score.save()

    @classmethod
    def auto_score_reliability(cls, comparison):
        """
        自动计算可靠性得分（基于历史履约数据）
        算法：基于历史订单的交期达成率和质量合格率
        """
        scores = comparison.scores.select_related('quotation__rfq_supplier__supplier').all()

        if not scores:
            return

        from apps.purchase.models import PurchaseOrder

        for score in scores:
            supplier = score.quotation.rfq_supplier.supplier

            # 获取该供应商的历史订单
            historical_pos = PurchaseOrder.objects.filter(
                supplier=supplier,
                status__in=['RECEIVED', 'PARTIAL_RECEIVED', 'COMPLETED'],
                is_deleted=False
            ).order_by('-order_date')[:20]  # 最近20单

            if not historical_pos:
                score.score_reliability = Decimal('75')  # 新供应商默认中等
                score.save()
                continue

            total_orders = historical_pos.count()
            on_time_count = 0
            quality_pass_count = 0

            for po in historical_pos:
                # 检查是否按时交货
                if po.actual_delivery_date and po.delivery_date:
                    if po.actual_delivery_date <= po.delivery_date:
                        on_time_count += 1
                else:
                    on_time_count += 0.5  # 无数据假设中等

                # 检查质量（简化：如果没有退货就算合格）
                # TODO: 集成质量检验数据
                quality_pass_count += 1

            # 计算可靠性得分
            on_time_rate = on_time_count / total_orders if total_orders > 0 else 0.75
            quality_rate = quality_pass_count / total_orders if total_orders > 0 else 0.75

            # 可靠性得分 = 交期达成率 * 60% + 质量合格率 * 40%
            reliability = on_time_rate * 0.6 + quality_rate * 0.4
            score.score_reliability = Decimal(str(reliability * 100))
            score.save()

        logger.info(f"Auto scored reliability for comparison {comparison.comparison_no}")

    @classmethod
    def calculate_multi_dimension_ranks(cls, comparison):
        """
        计算多维度排名（用于多维度推荐）
        """
        scores = list(comparison.scores.all())

        if not scores:
            return

        # 价格排名（从低到高）
        price_sorted = sorted(scores, key=lambda x: float(x.quotation.total_amount))
        for i, s in enumerate(price_sorted, 1):
            s.price_rank = i

        # 交期排名（从短到长）
        delivery_sorted = sorted(scores, key=lambda x: -float(x.score_delivery))
        for i, s in enumerate(delivery_sorted, 1):
            s.delivery_rank = i

        # 质量排名（从高到低）
        quality_sorted = sorted(scores, key=lambda x: -float(x.score_quality))
        for i, s in enumerate(quality_sorted, 1):
            s.quality_rank = i

        # 更新推荐类型
        for s in scores:
            if s.price_rank == 1:
                if s.recommend_type == '' or s.recommend_type == 'PRICE':
                    s.recommend_type = 'PRICE'
            if s.delivery_rank == 1:
                if s.recommend_type == '' or s.recommend_type == 'DELIVERY':
                    s.recommend_type = 'DELIVERY'
            if s.quality_rank == 1 and float(s.score_quality) > 0:
                if s.recommend_type == '' or s.recommend_type == 'QUALITY':
                    s.recommend_type = 'QUALITY'
            if s.ranking == 1:
                s.recommend_type = 'OVERALL'

            s.save()

        logger.info(f"Calculated multi-dimension ranks for comparison {comparison.comparison_no}")

    @classmethod
    def _assess_risks(cls, comparison):
        """评估风险并生成预警"""
        scores = comparison.scores.select_related('quotation').all()
        rfq = comparison.rfq

        risk_count = 0

        for score in scores:
            quotation = score.quotation
            warnings = []

            # 1. 交期风险检查
            for line in quotation.lines.filter(is_deleted=False):
                rfq_line = line.rfq_line
                if line.earliest_delivery_date and rfq_line.required_date:
                    delay_days = (line.earliest_delivery_date - rfq_line.required_date).days
                    if delay_days > RISK_THRESHOLDS['delivery_delay_days']:
                        warnings.append({
                            'type': 'DELIVERY_DELAY',
                            'level': 'HIGH' if delay_days > 14 else 'MEDIUM',
                            'message': f'物料 {rfq_line.item.sku} 交期延迟 {delay_days} 天',
                            'item_id': rfq_line.item.id
                        })

            # 2. 价格风险检查
            if quotation.price_change_rate and float(quotation.price_change_rate) > RISK_THRESHOLDS['price_increase_rate']:
                warnings.append({
                    'type': 'PRICE_INCREASE',
                    'level': 'MEDIUM',
                    'message': f'价格上涨 {quotation.price_change_rate:.1f}%'
                })

            # 3. 可靠性风险检查
            if float(score.score_reliability) < RISK_THRESHOLDS['min_reliability_score']:
                warnings.append({
                    'type': 'LOW_RELIABILITY',
                    'level': 'MEDIUM',
                    'message': f'供应商可靠性得分较低 ({score.score_reliability:.0f}分)'
                })

            score.risk_warnings = warnings
            score.save()

            if any(w['level'] == 'HIGH' for w in warnings):
                risk_count += 1

        # 更新比价单风险等级
        if risk_count > len(scores) * 0.5:
            comparison.risk_level = 'HIGH'
        elif risk_count > 0:
            comparison.risk_level = 'MEDIUM'
        else:
            comparison.risk_level = 'LOW'
        comparison.save()

    @classmethod
    def update_manual_scores(cls, score_id, quality_score=None, service_score=None, technical_score=None, notes=None):
        """
        手动更新质量、服务和技术评分
        
        Args:
            score_id: QuotationScore ID
            quality_score: 质量得分 (0-100)
            service_score: 服务得分 (0-100)
            technical_score: 技术能力得分 (0-100)
            notes: 评价说明
        """
        score = QuotationScore.objects.get(id=score_id)

        if quality_score is not None:
            score.score_quality = Decimal(str(quality_score))

        if service_score is not None:
            score.score_service = Decimal(str(service_score))

        if technical_score is not None:
            score.score_technical = Decimal(str(technical_score))

        if notes is not None:
            score.notes = notes

        score.save()

        # 重新计算综合得分
        cls.calculate_total_scores(score.comparison)
        cls.calculate_multi_dimension_ranks(score.comparison)

        return score

    @classmethod
    def calculate_total_scores(cls, comparison):
        """计算综合得分并排名"""
        scores = list(comparison.scores.all())

        # 计算每个报价的综合得分
        for score in scores:
            score.calculate_total_score()
            score.save()

        # 按综合得分排序并更新排名
        scores.sort(key=lambda x: float(x.total_score), reverse=True)

        for i, score in enumerate(scores, 1):
            score.ranking = i
            score.is_recommended = (i == 1)  # 第一名自动推荐
            score.save()

        # 更新推荐报价
        if scores:
            comparison.recommended_quotation = scores[0].quotation
            comparison.recommendation_reason = cls._generate_recommendation_reason(scores[0])
            comparison.save()

        logger.info(f"Calculated total scores for comparison {comparison.comparison_no}")

    @classmethod
    def _generate_recommendation_reason(cls, top_score):
        """生成推荐理由"""
        reasons = []
        quotation = top_score.quotation
        supplier = quotation.rfq_supplier.supplier

        reasons.append(f"综合得分最高: {top_score.total_score:.2f}分")

        if float(top_score.score_price) >= 90:
            reasons.append("价格具有明显优势")

        if float(top_score.score_delivery) >= 90:
            reasons.append("交期最短")

        if float(top_score.score_quality) >= 80:
            reasons.append("质量评价良好")

        if float(top_score.score_service) >= 80:
            reasons.append("服务评价良好")

        return "；".join(reasons)

    @classmethod
    def update_weights(cls, comparison_id, weights):
        """
        更新比价权重并重新计算
        
        Args:
            comparison_id: QuotationComparison ID
            weights: {'price': 40, 'quality': 25, 'delivery': 20, 'service': 15, 'technical': 0}
        """
        comparison = QuotationComparison.objects.get(id=comparison_id)

        # 验证权重总和为100
        total = sum(weights.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"权重总和必须为100，当前为{total}")

        comparison.weight_price = weights.get('price', comparison.weight_price)
        comparison.weight_quality = weights.get('quality', comparison.weight_quality)
        comparison.weight_delivery = weights.get('delivery', comparison.weight_delivery)
        comparison.weight_service = weights.get('service', comparison.weight_service)
        comparison.weight_technical = weights.get('technical', comparison.weight_technical)
        comparison.weight_template = 'CUSTOM'
        comparison.save()

        # 重新计算综合得分
        cls.calculate_total_scores(comparison)
        cls.calculate_multi_dimension_ranks(comparison)

        return comparison

    @classmethod
    def apply_weight_template(cls, comparison_id, template_name):
        """
        应用权重模板
        
        Args:
            comparison_id: QuotationComparison ID
            template_name: 模板名称 STANDARD/QUALITY_FIRST/DELIVERY_FIRST/PRICE_FIRST
        """
        if template_name not in WEIGHT_TEMPLATES:
            raise ValueError(f"无效的权重模板: {template_name}")

        weights = WEIGHT_TEMPLATES[template_name]
        comparison = QuotationComparison.objects.get(id=comparison_id)

        comparison.weight_template = template_name
        comparison.weight_price = weights['price']
        comparison.weight_quality = weights['quality']
        comparison.weight_delivery = weights['delivery']
        comparison.weight_service = weights['service']
        comparison.weight_technical = weights['technical']
        comparison.save()

        # 重新计算
        cls.calculate_total_scores(comparison)
        cls.calculate_multi_dimension_ranks(comparison)

        return comparison

    @classmethod
    def get_multi_dimension_recommendations(cls, comparison_id):
        """
        获取多维度推荐结果
        
        Returns:
            dict: {
                'overall': {...},  # 综合最优
                'price': {...},    # 价格最优
                'delivery': {...}, # 交期最优
                'quality': {...},  # 质量最优
            }
        """
        comparison = QuotationComparison.objects.get(id=comparison_id)
        scores = comparison.scores.select_related(
            'quotation__rfq_supplier__supplier'
        ).all()

        recommendations = {
            'overall': None,
            'price': None,
            'delivery': None,
            'quality': None,
        }

        for score in scores:
            supplier = score.quotation.rfq_supplier.supplier
            score_data = {
                'score_id': score.id,
                'quotation_id': score.quotation.id,
                'supplier_id': supplier.id,
                'supplier_name': supplier.name,
                'total_amount': float(score.quotation.total_amount),
                'total_score': float(score.total_score),
                'ranking': score.ranking,
                'scores': {
                    'price': float(score.score_price),
                    'quality': float(score.score_quality),
                    'delivery': float(score.score_delivery),
                    'service': float(score.score_service),
                    'technical': float(score.score_technical),
                    'reliability': float(score.score_reliability),
                },
                'ranks': {
                    'overall': score.ranking,
                    'price': score.price_rank,
                    'delivery': score.delivery_rank,
                    'quality': score.quality_rank,
                },
                'risk_warnings': score.risk_warnings,
            }

            if score.ranking == 1:
                recommendations['overall'] = score_data
            if score.price_rank == 1:
                recommendations['price'] = score_data
            if score.delivery_rank == 1:
                recommendations['delivery'] = score_data
            if score.quality_rank == 1:
                recommendations['quality'] = score_data

        return recommendations

    @classmethod
    def get_comparison_report(cls, comparison):
        """
        生成比价报告数据
        
        Returns:
            dict: 比价报告数据
        """
        scores = comparison.scores.select_related(
            'quotation__rfq_supplier__supplier'
        ).order_by('ranking')

        # 获取物料明细比较
        item_comparisons = cls._get_item_comparisons(comparison)

        report = {
            'comparison_no': comparison.comparison_no,
            'rfq_no': comparison.rfq.rfq_no,
            'project_name': comparison.rfq.project.name if comparison.rfq.project else None,
            'created_at': comparison.created_at.isoformat() if comparison.created_at else None,
            'status': comparison.status,
            'status_display': comparison.get_status_display(),

            # 非标自动化增强字段
            'comparison_type': comparison.comparison_type,
            'comparison_type_display': comparison.get_comparison_type_display(),
            'risk_level': comparison.risk_level,
            'risk_level_display': comparison.get_risk_level_display(),
            'critical_items_count': comparison.critical_items_count,
            'long_lead_items_count': comparison.long_lead_items_count,
            'weight_template': comparison.weight_template,
            'weight_template_display': comparison.get_weight_template_display(),

            'weights': {
                'price': float(comparison.weight_price),
                'quality': float(comparison.weight_quality),
                'delivery': float(comparison.weight_delivery),
                'service': float(comparison.weight_service),
                'technical': float(comparison.weight_technical),
            },

            'price_summary': {
                'min': float(comparison.min_price) if comparison.min_price else 0,
                'max': float(comparison.max_price) if comparison.max_price else 0,
                'avg': float(comparison.avg_price) if comparison.avg_price else 0,
                'spread': float(comparison.max_price - comparison.min_price) if comparison.min_price and comparison.max_price else 0,
            },

            'suppliers': [],
            'recommended': None,
            'multi_recommendations': cls.get_multi_dimension_recommendations(comparison.id),
            'item_comparisons': item_comparisons,
        }

        for score in scores:
            quotation = score.quotation
            supplier = quotation.rfq_supplier.supplier

            supplier_data = {
                'score_id': score.id,
                'ranking': score.ranking,
                'is_recommended': score.is_recommended,

                'supplier_id': supplier.id,
                'supplier_name': supplier.name,
                'supplier_code': supplier.code,

                'quotation_id': quotation.id,
                'quotation_no': quotation.quotation_no,
                'quotation_date': quotation.quotation_date.isoformat() if quotation.quotation_date else None,
                'valid_until': quotation.valid_until.isoformat() if quotation.valid_until else None,

                'total_amount': float(quotation.total_amount),
                'total_with_tax': float(quotation.total_with_tax),
                'tax_rate': quotation.tax_rate,

                'payment_terms': quotation.payment_terms,
                'delivery_terms': quotation.delivery_terms,
                'warranty_period': quotation.warranty_period,

                'price_change_rate': float(quotation.price_change_rate) if quotation.price_change_rate else None,

                'scores': {
                    'price': float(score.score_price),
                    'quality': float(score.score_quality),
                    'delivery': float(score.score_delivery),
                    'service': float(score.score_service),
                    'technical': float(score.score_technical),
                    'reliability': float(score.score_reliability),
                    'total': float(score.total_score),
                },

                'ranks': {
                    'overall': score.ranking,
                    'price': score.price_rank,
                    'delivery': score.delivery_rank,
                    'quality': score.quality_rank,
                },

                'recommend_type': score.recommend_type,
                'risk_warnings': score.risk_warnings,
                'notes': score.notes,
            }

            report['suppliers'].append(supplier_data)

            if score.is_recommended:
                report['recommended'] = supplier_data

        report['recommendation_reason'] = comparison.recommendation_reason
        report['total_suppliers'] = len(report['suppliers'])

        return report

    @classmethod
    def _get_item_comparisons(cls, comparison):
        """获取物料明细比较数据"""
        rfq = comparison.rfq
        item_data = {}

        # 获取所有RFQ明细
        for rfq_line in rfq.lines.filter(is_deleted=False):
            item = rfq_line.item
            item_key = item.id

            if item_key not in item_data:
                item_data[item_key] = {
                    'item_id': item.id,
                    'item_sku': item.sku,
                    'item_name': item.name,
                    'required_qty': float(rfq_line.qty),
                    'required_date': rfq_line.required_date.isoformat() if rfq_line.required_date else None,
                    'supplier_prices': [],
                    'min_price': None,
                    'max_price': None,
                    'avg_price': None,
                }

            # 获取各供应商对此物料的报价
            for score in comparison.scores.all():
                quotation = score.quotation
                quot_line = quotation.lines.filter(rfq_line=rfq_line).first()

                if quot_line:
                    supplier = quotation.rfq_supplier.supplier

                    price_info = {
                        'supplier_id': supplier.id,
                        'supplier_name': supplier.name,
                        'unit_price': float(quot_line.unit_price),
                        'unit_price_with_tax': float(quot_line.unit_price_with_tax),
                        'qty': float(quot_line.qty),
                        'lead_time_days': quot_line.lead_time_days,
                        'is_alternative': quot_line.is_alternative,
                        'alternative_brand': quot_line.alternative_brand,
                        'last_unit_price': float(quot_line.last_unit_price) if quot_line.last_unit_price else None,
                        'price_change_rate': float(quot_line.price_change_rate) if quot_line.price_change_rate else None,
                    }

                    item_data[item_key]['supplier_prices'].append(price_info)

        # 计算每个物料的价格统计
        for item_key, data in item_data.items():
            prices = [p['unit_price'] for p in data['supplier_prices']]
            if prices:
                data['min_price'] = min(prices)
                data['max_price'] = max(prices)
                data['avg_price'] = sum(prices) / len(prices)

        return list(item_data.values())

    @classmethod
    def complete_comparison(cls, comparison_id):
        """完成比价分析"""
        comparison = QuotationComparison.objects.get(id=comparison_id)
        comparison.status = 'COMPLETED'
        comparison.save()

        logger.info(f"Completed comparison {comparison.comparison_no}")
        return comparison

    @classmethod
    def approve_comparison(cls, comparison_id, user, notes=None):
        """审批比价分析"""
        comparison = QuotationComparison.objects.get(id=comparison_id)

        if comparison.status not in ['COMPLETED', 'IN_PROGRESS']:
            raise ValueError("只能审批已完成或进行中的比价分析")

        comparison.status = 'APPROVED'
        comparison.approved_by = user
        comparison.approved_at = timezone.now()

        if notes:
            comparison.notes = notes

        comparison.save()

        # 更新推荐报价的状态
        if comparison.recommended_quotation:
            comparison.recommended_quotation.status = 'ACCEPTED'
            comparison.recommended_quotation.save()

        logger.info(f"Approved comparison {comparison.comparison_no} by {user.username}")
        return comparison

    @classmethod
    def convert_to_po(cls, comparison_id, user):
        """
        将推荐报价转换为采购订单
        
        Returns:
            PurchaseOrder instance
        """
        from .models import PurchaseOrder, PurchaseOrderLine

        comparison = QuotationComparison.objects.get(id=comparison_id)

        if comparison.status != 'APPROVED':
            raise ValueError("只能将已审批的比价分析转换为采购订单")

        if not comparison.recommended_quotation:
            raise ValueError("没有推荐的报价")

        quotation = comparison.recommended_quotation
        rfq = comparison.rfq

        with transaction.atomic():
            # 创建采购订单
            po = PurchaseOrder.objects.create(
                supplier=quotation.rfq_supplier.supplier,
                project=rfq.project,
                delivery_date=timezone.now().date(),
                payment_terms=quotation.payment_terms,
                tax_rate=quotation.tax_rate,
                created_by=user
            )

            # 创建订单明细
            total_amount = Decimal('0')
            for quot_line in quotation.lines.filter(is_deleted=False):
                line = PurchaseOrderLine.objects.create(
                    po=po,
                    item=quot_line.rfq_line.item,
                    qty=quot_line.qty,
                    unit_price=quot_line.unit_price,
                    created_by=user
                )
                total_amount += line.line_amount

            # 更新采购订单金额
            po.total_amount = total_amount
            po.tax_amount = total_amount * po.tax_rate / 100
            po.total_with_tax = total_amount + po.tax_amount
            po.save()

            # 记录价格历史
            cls._record_price_history(po)

            logger.info(f"Converted comparison {comparison.comparison_no} to PO {po.order_no}")

        return po

    @classmethod
    def _record_price_history(cls, po):
        """记录采购价格历史"""
        for line in po.lines.filter(is_deleted=False):
            ItemPriceHistory.objects.create(
                item=line.item,
                supplier=po.supplier,
                unit_price=line.unit_price,
                qty=line.qty,
                tax_rate=po.tax_rate,
                source_type='PO',
                source_id=po.id,
                source_no=po.order_no,
                price_date=po.order_date,
                created_by=po.created_by
            )

    @classmethod
    def get_item_price_history(cls, item_id, supplier_id=None, limit=10):
        """
        获取物料价格历史
        
        Args:
            item_id: 物料ID
            supplier_id: 可选的供应商ID
            limit: 返回记录数
        
        Returns:
            list: 价格历史记录
        """
        queryset = ItemPriceHistory.objects.filter(
            item_id=item_id,
            is_deleted=False
        ).order_by('-price_date')

        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        history = []
        for record in queryset[:limit]:
            history.append({
                'id': record.id,
                'supplier_name': record.supplier.name,
                'unit_price': float(record.unit_price),
                'qty': float(record.qty),
                'tax_rate': record.tax_rate,
                'source_type': record.source_type,
                'source_no': record.source_no,
                'price_date': record.price_date.isoformat(),
            })

        return history

    @classmethod
    def get_last_purchase_price(cls, item_id, supplier_id):
        """获取物料的上次采购价格"""
        record = ItemPriceHistory.objects.filter(
            item_id=item_id,
            supplier_id=supplier_id,
            is_deleted=False
        ).order_by('-price_date').first()

        return float(record.unit_price) if record else None

