from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """
    A public "is the server up?" address for uptime monitors and the host's health check.
    It does no database work, so it answers quickly and never reveals any data.
    """
    return JsonResponse({"status": "ok"})
