from apps.authentication.drf import BusinessRouter

from .views import (
    InternalProfitDistributionViewSet,
    LegalLedgerViewSet,
    RealEstateAccountingLinkViewSet,
    RealEstateFileViewSet,
    RealEstateTransactionViewSet,
    TransactionPartyViewSet,
)

router = BusinessRouter()
router.register('transactions', RealEstateTransactionViewSet, basename='real-estate-transaction')
router.register('parties', TransactionPartyViewSet, basename='real-estate-party')
router.register('ledgers', LegalLedgerViewSet, basename='real-estate-ledger')
router.register('files', RealEstateFileViewSet, basename='real-estate-file')
router.register('accounting-links', RealEstateAccountingLinkViewSet, basename='real-estate-accounting-link')
router.register('profit-distributions', InternalProfitDistributionViewSet, basename='real-estate-profit')

urlpatterns = router.urls
