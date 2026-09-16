from .models import FamilyMember

# 双方向に同じ意味を持つ関係のみ自動で逆リンクを作る。親子など非対称な関係は
# 相手側の性別等から自動判定できないため対象外（スタッフが手動で追加する）。
SYMMETRIC_RELATIONSHIPS = {FamilyMember.RELATIONSHIP_SPOUSE, FamilyMember.RELATIONSHIP_SIBLING}


def sync_reverse_family_link(family_member):
    if not family_member.family_customer_id:
        return
    if family_member.relationship not in SYMMETRIC_RELATIONSHIPS:
        return
    reverse_exists = FamilyMember.objects.filter(
        customer_id=family_member.family_customer_id,
        family_customer_id=family_member.customer_id,
    ).exists()
    if reverse_exists:
        return
    FamilyMember.objects.create(
        customer_id=family_member.family_customer_id,
        family_customer_id=family_member.customer_id,
        relationship=family_member.relationship,
    )
