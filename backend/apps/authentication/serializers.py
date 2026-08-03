from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


def _run_password_validators(value, user=None):
    try:
        password_validation.validate_password(value, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return value


class SystemUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser',
            'last_login', 'date_joined',
        ]
        read_only_fields = fields


class SystemUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name']

    def validate_password(self, value):
        return _run_password_validators(value)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangeOwnPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('現在のパスワードが正しくありません。')
        return value

    def validate_new_password(self, value):
        return _run_password_validators(value, user=self.context['request'].user)

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        return _run_password_validators(value, user=self.instance)

    def save(self):
        self.instance.set_password(self.validated_data['new_password'])
        self.instance.save(update_fields=['password'])
        return self.instance
