from django.conf import settings
from rest_framework import mixins, serializers, viewsets

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

    def _account_holder(self):
        """
        Whose transaction this is: the signed-in user, except in DEMO_MODE where staff may send
        `"on_behalf_of": "<customer email>"` to act as one of the demo customers.
        """
        email = str(self.request.data.get("on_behalf_of") or "").strip().lower()
        if not email:
            return self.request.user
        if not (settings.DEMO_MODE and self.request.user.is_analyst_or_admin):
            raise serializers.ValidationError({"on_behalf_of": "Only staff can do this, and only in demo mode."})
        from authentication.models import User

        customer = User.objects.filter(email__iexact=email, role=User.Role.CUSTOMER, is_active=True).first()
        if customer is None:
            raise serializers.ValidationError({"on_behalf_of": "No customer with that email."})
        return customer

    def perform_create(self, serializer):
        transaction = serializer.save(
            user=self._account_holder(),
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
