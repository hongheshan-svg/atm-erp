from rest_framework.response import Response
from rest_framework.views import APIView

from .services.workbench import summary


class WorkbenchView(APIView):
    def get(self, request):
        return Response(summary(request))
