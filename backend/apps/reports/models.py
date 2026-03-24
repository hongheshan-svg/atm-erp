"""
Reports app - doesn't need models, uses services for calculations.
"""
from django.db import models

# No models needed - this app provides calculation services


# Import new improvement module models
from .report_builder import ReportTemplate, ReportExecution, ReportFavorite  # noqa: E402, F401
from .prediction import PredictionModel, PredictionResult, RiskAlert  # noqa: E402, F401
