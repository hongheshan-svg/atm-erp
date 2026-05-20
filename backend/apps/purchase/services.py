"""
Purchase services for budget validation and other business logic.
"""

from decimal import Decimal

from django.db.models import F, Sum


class BudgetValidationService:
    """
    Service for validating purchase requests against project budgets.
    """

    @classmethod
    def get_project_material_budget(cls, project):
        """Get the total material budget for a project."""
        return project.budget_material or Decimal('0')

    @classmethod
    def get_project_used_material_budget(cls, project):
        """
        Get the amount already used from material budget.
        Includes: approved/converted purchase requests + completed stock moves for the project.
        """
        from apps.inventory.models import StockMove

        from .models import PurchaseRequest

        # Sum of approved/converted purchase requests
        pr_total = PurchaseRequest.objects.filter(
            project=project, status__in=['APPROVED', 'CONVERTED'], is_deleted=False
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        # Sum of completed project material moves (actual cost)
        move_total = StockMove.objects.filter(
            project=project, move_type='OUT_PROJECT', status='COMPLETED', is_deleted=False
        ).aggregate(total=Sum(F('qty') * F('unit_cost')))['total'] or Decimal('0')

        # Return the higher of the two (to avoid double counting)
        # In practice, PR amounts are estimates, actual moves are real costs
        return max(pr_total, move_total)

    @classmethod
    def get_project_remaining_material_budget(cls, project):
        """Get the remaining material budget for a project."""
        total_budget = cls.get_project_material_budget(project)
        used_budget = cls.get_project_used_material_budget(project)
        return total_budget - used_budget

    @classmethod
    def validate_purchase_request(cls, project, request_amount, exclude_pr_id=None):
        """
        Validate if a purchase request amount is within budget.

        Args:
            project: The Project instance
            request_amount: The amount of the purchase request
            exclude_pr_id: Exclude this PR from used budget calculation (for updates)

        Returns:
            dict with validation result and details
        """
        if not project:
            return {
                'valid': True,
                'message': '未关联项目，无需预算校验',
                'budget_total': None,
                'budget_used': None,
                'budget_remaining': None,
                'request_amount': float(request_amount),
            }

        total_budget = cls.get_project_material_budget(project)

        # If no budget set, allow any amount but warn
        if total_budget <= 0:
            return {
                'valid': True,
                'warning': True,
                'message': f'项目 {project.code} 未设置材料预算',
                'budget_total': 0,
                'budget_used': 0,
                'budget_remaining': 0,
                'request_amount': float(request_amount),
            }

        # Calculate used budget, excluding current PR if updating
        used_budget = cls.get_project_used_material_budget(project)

        if exclude_pr_id:
            from .models import PurchaseRequest

            excluded_pr = PurchaseRequest.objects.filter(
                id=exclude_pr_id, status__in=['APPROVED', 'CONVERTED'], is_deleted=False
            ).first()
            if excluded_pr:
                used_budget -= excluded_pr.total_amount

        remaining_budget = total_budget - used_budget

        is_valid = request_amount <= remaining_budget

        if is_valid:
            message = f'预算校验通过。剩余预算: ¥{remaining_budget:,.2f}'
        else:
            over_amount = request_amount - remaining_budget
            message = f'超出材料预算 ¥{over_amount:,.2f}。剩余预算: ¥{remaining_budget:,.2f}'

        return {
            'valid': is_valid,
            'message': message,
            'budget_total': float(total_budget),
            'budget_used': float(used_budget),
            'budget_remaining': float(remaining_budget),
            'request_amount': float(request_amount),
            'over_budget': float(request_amount - remaining_budget) if not is_valid else 0,
        }

    @classmethod
    def get_project_budget_summary(cls, project):
        """
        Get a complete budget summary for a project.
        """
        from apps.finance.models import Expense
        from apps.projects.models import ProjectMember

        # Material budget
        material_budget = project.budget_material or Decimal('0')
        material_used = cls.get_project_used_material_budget(project)

        # Labor budget
        labor_budget = project.budget_labor or Decimal('0')
        labor_used = ProjectMember.objects.filter(project=project, is_deleted=False).aggregate(
            total=Sum(F('actual_hours') * F('hourly_rate'))
        )['total'] or Decimal('0')

        # Expense budget
        expense_budget = project.budget_expense or Decimal('0')
        expense_used = Expense.objects.filter(
            project=project, status__in=['APPROVED', 'REIMBURSED'], is_deleted=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Total
        total_budget = project.budget_total or (material_budget + labor_budget + expense_budget)
        total_used = material_used + labor_used + expense_used

        return {
            'project_code': project.code,
            'project_name': project.name,
            'material': {
                'budget': float(material_budget),
                'used': float(material_used),
                'remaining': float(material_budget - material_used),
                'utilization': float(material_used / material_budget * 100) if material_budget > 0 else 0,
            },
            'labor': {
                'budget': float(labor_budget),
                'used': float(labor_used),
                'remaining': float(labor_budget - labor_used),
                'utilization': float(labor_used / labor_budget * 100) if labor_budget > 0 else 0,
            },
            'expense': {
                'budget': float(expense_budget),
                'used': float(expense_used),
                'remaining': float(expense_budget - expense_used),
                'utilization': float(expense_used / expense_budget * 100) if expense_budget > 0 else 0,
            },
            'total': {
                'budget': float(total_budget),
                'used': float(total_used),
                'remaining': float(total_budget - total_used),
                'utilization': float(total_used / total_budget * 100) if total_budget > 0 else 0,
            },
        }
