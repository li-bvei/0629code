from .models import ResidenceStatusMaster

# 出入国在留管理庁公表の在留資格一覧（活動類型別）を参照。
# 高度専門職・特定技能・技能実習は号（1号イ/ロ/ハ、2号など）をまとめて1件にしている
# ——CaseTypeMaster（案件種別）側もサブタイプまで分けていないので、粒度を揃えている。
STANDARD_RESIDENCE_STATUSES = [
    # 就労が認められる在留資格
    ('外交', ResidenceStatusMaster.CATEGORY_WORK),
    ('公用', ResidenceStatusMaster.CATEGORY_WORK),
    ('教授', ResidenceStatusMaster.CATEGORY_WORK),
    ('芸術', ResidenceStatusMaster.CATEGORY_WORK),
    ('宗教', ResidenceStatusMaster.CATEGORY_WORK),
    ('報道', ResidenceStatusMaster.CATEGORY_WORK),
    ('高度専門職', ResidenceStatusMaster.CATEGORY_WORK),
    ('経営・管理', ResidenceStatusMaster.CATEGORY_WORK),
    ('法律・会計業務', ResidenceStatusMaster.CATEGORY_WORK),
    ('医療', ResidenceStatusMaster.CATEGORY_WORK),
    ('研究', ResidenceStatusMaster.CATEGORY_WORK),
    ('教育', ResidenceStatusMaster.CATEGORY_WORK),
    ('技術・人文知識・国際業務', ResidenceStatusMaster.CATEGORY_WORK),
    ('企業内転勤', ResidenceStatusMaster.CATEGORY_WORK),
    ('介護', ResidenceStatusMaster.CATEGORY_WORK),
    ('興行', ResidenceStatusMaster.CATEGORY_WORK),
    ('技能', ResidenceStatusMaster.CATEGORY_WORK),
    ('特定技能', ResidenceStatusMaster.CATEGORY_WORK),
    ('技能実習', ResidenceStatusMaster.CATEGORY_WORK),
    # 就労が認められない在留資格（原則）
    ('文化活動', ResidenceStatusMaster.CATEGORY_NON_WORK),
    ('短期滞在', ResidenceStatusMaster.CATEGORY_NON_WORK),
    ('留学', ResidenceStatusMaster.CATEGORY_NON_WORK),
    ('研修', ResidenceStatusMaster.CATEGORY_NON_WORK),
    ('家族滞在', ResidenceStatusMaster.CATEGORY_NON_WORK),
    # 身分・地位に基づく在留資格（活動制限なし）
    ('永住者', ResidenceStatusMaster.CATEGORY_STATUS),
    ('日本人の配偶者等', ResidenceStatusMaster.CATEGORY_STATUS),
    ('永住者の配偶者等', ResidenceStatusMaster.CATEGORY_STATUS),
    ('定住者', ResidenceStatusMaster.CATEGORY_STATUS),
    # 特定活動
    ('特定活動', ResidenceStatusMaster.CATEGORY_SPECIFIED),
    ('その他', ResidenceStatusMaster.CATEGORY_SPECIFIED),
]


def seed_standard_residence_statuses():
    result = {'success': True, 'message': '在留資格を取り込みました。', 'created': 0, 'skipped': 0}
    for index, (name, category) in enumerate(STANDARD_RESIDENCE_STATUSES, start=1):
        _, created = ResidenceStatusMaster.objects.get_or_create(
            name=name,
            defaults={'category': category, 'sort_order': index * 10},
        )
        if created:
            result['created'] += 1
        else:
            result['skipped'] += 1
    return result
