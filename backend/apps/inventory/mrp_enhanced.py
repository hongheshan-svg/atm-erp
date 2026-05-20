"""
Enhanced MRP with BOM Explosion
"""
from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class MRPExplosionService:
    """Enhanced MRP BOM explosion service."""

    @staticmethod
    def explode_bom(project_id):
        from apps.inventory.models import Stock
        from apps.projects.models import BOM

        requirements = []
        bom_items = BOM.objects.filter(
            project_id=project_id, is_deleted=False
        ).select_related('material')

        for item in bom_items:
            material = getattr(item, 'material', None)
            material_code = getattr(material, 'code', '') if material else getattr(item, 'material_code', '')
            material_name = getattr(material, 'name', '') if material else getattr(item, 'material_name', '')
            required_qty = getattr(item, 'quantity', Decimal('0'))

            current_stock = Decimal('0')
            try:
                stock = Stock.objects.filter(
                    material_code=material_code, is_deleted=False
                ).first()
                if stock:
                    current_stock = getattr(stock, 'quantity', Decimal('0'))
            except Exception:
                pass

            shortage = max(required_qty - current_stock, Decimal('0'))

            requirements.append({
                'material_code': material_code,
                'material_name': material_name,
                'bom_level': getattr(item, 'level', 0),
                'required_quantity': str(required_qty),
                'current_stock': str(current_stock),
                'shortage': str(shortage),
                'unit_price': str(getattr(material, 'unit_price', Decimal('0.00')) if material else Decimal('0.00')),
                'estimated_cost': str(shortage * (getattr(material, 'unit_price', Decimal('0.00')) if material else Decimal('0.00'))),
            })

        return requirements


class MRPExplosionView(APIView):
    """POST: Explode BOM for a project and return material requirements."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': '项目ID必填'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            requirements = MRPExplosionService.explode_bom(project_id)
            return Response({
                'project_id': project_id,
                'total_items': len(requirements),
                'requirements': requirements,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MRPAutoGenerateView(APIView):
    """POST: Auto-generate purchase requisitions from MRP explosion."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': '项目ID必填'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            requirements = MRPExplosionService.explode_bom(project_id)
            shortages = [r for r in requirements if Decimal(r['shortage']) > 0]

            created_requisitions = []
            for item in shortages:
                try:
                    from apps.purchase.models import PurchaseRequisition
                    pr = PurchaseRequisition.objects.create(
                        material_code=item['material_code'],
                        material_name=item['material_name'],
                        quantity=Decimal(item['shortage']),
                        estimated_price=Decimal(item['estimated_cost']),
                        project_id=project_id,
                        created_by=request.user,
                    )
                    created_requisitions.append({
                        'id': pr.id,
                        'material_code': item['material_code'],
                        'quantity': item['shortage'],
                    })
                except Exception:
                    created_requisitions.append({
                        'material_code': item['material_code'],
                        'quantity': item['shortage'],
                        'status': 'skipped_model_not_found',
                    })

            return Response({
                'project_id': project_id,
                'total_shortages': len(shortages),
                'created_requisitions': created_requisitions,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
