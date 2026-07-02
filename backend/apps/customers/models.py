from django.db import models


class Customer(models.Model):
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'

    GENDER_CHOICES = [
        (GENDER_MALE, '男性'),
        (GENDER_FEMALE, '女性'),
        (GENDER_OTHER, 'その他'),
    ]

    name = models.CharField(max_length=100)
    name_kana = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    residence_status = models.CharField(max_length=100, blank=True)
    residence_card_no = models.CharField(max_length=50, blank=True)
    residence_expiry = models.DateField(null=True, blank=True)
    passport_no = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    postal_code = models.CharField('郵便番号', max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    my_number = models.CharField('マイナンバー', max_length=30, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers'
        ordering = ['name']

    def __str__(self):
        return self.name


class FamilyMember(models.Model):
    RELATIONSHIP_SPOUSE = 'spouse'
    RELATIONSHIP_CHILD = 'child'
    RELATIONSHIP_FATHER = 'father'
    RELATIONSHIP_MOTHER = 'mother'
    RELATIONSHIP_SIBLING = 'sibling'
    RELATIONSHIP_OTHER = 'other'

    RELATIONSHIP_CHOICES = [
        (RELATIONSHIP_SPOUSE, '配偶者'),
        (RELATIONSHIP_CHILD, '子'),
        (RELATIONSHIP_FATHER, '父'),
        (RELATIONSHIP_MOTHER, '母'),
        (RELATIONSHIP_SIBLING, '兄弟姉妹'),
        (RELATIONSHIP_OTHER, 'その他'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='family_members',
    )
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    name = models.CharField(max_length=100)
    name_kana = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Customer.GENDER_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    residence_status = models.CharField(max_length=100, blank=True)
    residence_card_no = models.CharField(max_length=50, blank=True)
    residence_expiry = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    postal_code = models.CharField('郵便番号', max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    my_number = models.CharField('マイナンバー', max_length=30, blank=True)
    is_dependent = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'family_members'
        ordering = ['customer', 'relationship', 'name']

    def __str__(self):
        return f'{self.customer.name} - {self.get_relationship_display()} - {self.name}'
