"""
Reports app - doesn't need models, uses services for calculations.
"""

# No models needed - this app provides calculation services


# Import new improvement module models
from .prediction import PredictionModel, PredictionResult, RiskAlert  # noqa: E402, F401
from .report_builder import ReportExecution, ReportFavorite, ReportTemplate  # noqa: E402, F401
