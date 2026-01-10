"""
报价比价分析服务
Quotation Comparison Service
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, Sum
from django.utils import timezone

from .rfq_models import (
    RFQ, SupplierQuotation, QuotationComparison, 
    QuotationScore, ItemPriceHistory
)

logger = logging.getLogger(__name__)


class QuotationComparisonService:
    """报价比价分析服务"""
    
    @classmethod
    def create_comparison(cls, rfq_id, user, weights=None):
        """
        创建比价分析
        
        Args:
            rfq_id: 询价单ID
            user: 创建用户
            weights: 可选的权重配置 {'price': 40, 'quality': 25, 'delivery': 20, 'service': 15}
        
        Returns:
            QuotationComparison instance
        """
        rfq = RFQ.objects.get(id=rfq_id)
        
        # 检查是否有已提交的报价
        quotations = SupplierQuotation.objects.filter(
            rfq_supplier__rfq=rfq,
            status='SUBMITTED',
            is_deleted=False
        )
        
        if quotations.count() < 2:
            raise ValueError("至少需要2个供应商报价才能进行比价分析")
        
        with transaction.atomic():
            # 创建比价分析
            comparison_data = {
                'rfq': rfq,
                'created_by': user,
                'status': 'IN_PROGRESS',
            }
            
            if weights:
                comparison_data.update({
                    'weight_price': weights.get('price', 40),
                    'weight_quality': weights.get('quality', 25),
                    'weight_delivery': weights.get('delivery', 20),
                    'weight_service': weights.get('service', 15),
                })
            
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
            
            # 自动评分
            cls.auto_score(comparison)
            
            logger.info(f"Created comparison {comparison.comparison_no} for RFQ {rfq.rfq_no}")
        
        return comparison
    
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
        """自动评分（价格和交期）"""
        cls.auto_score_price(comparison)
        cls.auto_score_delivery(comparison)
        cls.calculate_total_scores(comparison)
    
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
    def update_manual_scores(cls, score_id, quality_score=None, service_score=None, notes=None):
        """
        手动更新质量和服务评分
        
        Args:
            score_id: QuotationScore ID
            quality_score: 质量得分 (0-100)
            service_score: 服务得分 (0-100)
            notes: 评价说明
        """
        score = QuotationScore.objects.get(id=score_id)
        
        if quality_score is not None:
            score.score_quality = Decimal(str(quality_score))
        
        if service_score is not None:
            score.score_service = Decimal(str(service_score))
        
        if notes is not None:
            score.notes = notes
        
        score.save()
        
        # 重新计算综合得分
        cls.calculate_total_scores(score.comparison)
        
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
            weights: {'price': 40, 'quality': 25, 'delivery': 20, 'service': 15}
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
        comparison.save()
        
        # 重新计算综合得分
        cls.calculate_total_scores(comparison)
        
        return comparison
    
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
            
            'weights': {
                'price': float(comparison.weight_price),
                'quality': float(comparison.weight_quality),
                'delivery': float(comparison.weight_delivery),
                'service': float(comparison.weight_service),
            },
            
            'price_summary': {
                'min': float(comparison.min_price) if comparison.min_price else 0,
                'max': float(comparison.max_price) if comparison.max_price else 0,
                'avg': float(comparison.avg_price) if comparison.avg_price else 0,
                'spread': float(comparison.max_price - comparison.min_price) if comparison.min_price and comparison.max_price else 0,
            },
            
            'suppliers': [],
            'recommended': None,
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
                    'total': float(score.total_score),
                },
                
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

