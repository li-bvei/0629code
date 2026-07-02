from rest_framework import serializers

from .models import Customer, FamilyMember


class CustomerSerializer(serializers.ModelSerializer):
    cases_count = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'name_kana',
            'birth_date',
            'gender',
            'nationality',
            'residence_status',
            'residence_card_no',
            'residence_expiry',
            'passport_no',
            'passport_expiry',
            'email',
            'phone',
            'postal_code',
            'address',
            'my_number',
            'note',
            'cases_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'cases_count', 'created_at', 'updated_at']

    def get_cases_count(self, obj):
        return obj.cases.count()


class FamilyMemberSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = FamilyMember
        fields = [
            'id',
            'customer',
            'customer_name',
            'relationship',
            'relationship_display',
            'name',
            'name_kana',
            'birth_date',
            'gender',
            'gender_display',
            'nationality',
            'residence_status',
            'residence_card_no',
            'residence_expiry',
            'phone',
            'postal_code',
            'address',
            'my_number',
            'is_dependent',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'relationship_display',
            'gender_display',
            'created_at',
            'updated_at',
        ]
