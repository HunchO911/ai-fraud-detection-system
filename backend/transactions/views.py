from rest_framework import mixins, viewsets

from detection.services import process_transaction

from .models import Transaction
from .serializers import TransactionSerializer


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/transactions/        submit a transaction (it is scored straight away)
    GET  /api/transactions/        list (paginated)
    GET  /api/transactions/<id>/   one transaction

    Transactions are never edited or deleted through the API (audit trail), which
    is why only create / list / retrieve are mixed in.
    """

    serializer_class = TransactionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.select_related("user", "detection_result")
        # Analysts and admins see everything; customers only see their own.
        if user.is_analyst_or_admin:
            return queryset
        return queryset.filter(user=user)

    def perform_create(self, serializer):
        transaction = serializer.save(
            user=self.request.user,
            ip_address=self._client_ip(),
        )
        # Run the AI model right away. This also sends the email / SMS alerts when
        # the risk is high enough. It never raises: if the model is missing or
        # fails, the transaction stays "pending" and the API still answers 201.
        process_transaction(transaction)
        return transaction

    def _client_ip(self):
        # REMOTE_ADDR is the only address a client can't fake. Behind a reverse
        # proxy, configure the proxy / Django to expose the real client address
        # rather than trusting an X-Forwarded-For header blindly.
        return self.request.META.get("REMOTE_ADDR")
