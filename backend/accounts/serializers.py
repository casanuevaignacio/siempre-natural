import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import CustomerAccount


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
        max_length=128,
    )

    def validate_email(self, value):
        value = value.strip().casefold()
        if CustomerAccount.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este correo."
            )
        return value

    def validate(self, attrs):
        candidate_user = get_user_model()(email=attrs["email"])
        validate_password(attrs["password"], user=candidate_user)
        return attrs

    def create(self, validated_data):
        user_model = get_user_model()
        email = validated_data["email"]
        user = user_model.objects.create_user(
            username=uuid.uuid4().hex,
            email=email,
            password=validated_data["password"],
        )
        return CustomerAccount.objects.create(user=user, email=email)


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
        max_length=128,
    )


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class CustomerOrderItemSerializer(serializers.Serializer):
    name = serializers.CharField(source="product_name")
    quantity_grams = serializers.IntegerField()
    quantity_units = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=0)


class CustomerOrderHistorySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=14, decimal_places=0)
    status = serializers.CharField(source="get_status_display")
    delivery_mode = serializers.CharField(source="get_delivery_mode_display")
    items = CustomerOrderItemSerializer(many=True)
