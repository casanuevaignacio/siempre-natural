from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .notifications import send_order_notification
from .serializers import OrderCreateSerializer, OrderCreatedSerializer


@method_decorator(csrf_protect, name="dispatch")
class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderCreateSerializer
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderCreatedSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        email_notification_sent = send_order_notification(order)
        response_data = dict(OrderCreatedSerializer(order).data)
        response_data["email_notification_sent"] = email_notification_sent
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )
