from django.contrib import admin

from .models import Customer, FamilyMember, ResidenceStatusMaster


@admin.register(ResidenceStatusMaster)
class ResidenceStatusMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'sort_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'name_kana',
        'birth_date',
        'gender',
        'nationality',
        'residence_status',
        'phone',
        'postal_code',
        'updated_at',
    )
    search_fields = (
        'name',
        'name_kana',
        'email',
        'phone',
        'postal_code',
        'residence_card_no',
        'passport_no',
    )
    list_filter = ('gender', 'nationality', 'residence_status')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'customer',
        'relationship',
        'birth_date',
        'gender',
        'nationality',
        'residence_status',
        'residence_expiry',
        'is_dependent',
        'updated_at',
    )
    search_fields = (
        'name',
        'name_kana',
        'customer__name',
        'phone',
        'postal_code',
        'residence_card_no',
    )
    list_filter = (
        'relationship',
        'gender',
        'is_dependent',
        'nationality',
        'residence_status',
    )
    readonly_fields = ('created_at', 'updated_at')
