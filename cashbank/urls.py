from django.urls import path

from cashbank import views

app_name = 'cashbank'

urlpatterns = [
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/new/', views.account_create, name='account_create'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/incoming/new/', views.transaction_create, {'transaction_type': 'incoming'}, name='incoming_create'),
    path('transactions/outgoing/new/', views.transaction_create, {'transaction_type': 'outgoing'}, name='outgoing_create'),
    path('transactions/transfer/new/', views.transfer_create, name='transfer_create'),
    path('transactions/<uuid:uuid>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<uuid:uuid>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<uuid:uuid>/post/', views.transaction_post, name='transaction_post'),
    path('transactions/<uuid:uuid>/reverse/', views.transaction_reverse, name='transaction_reverse'),
    path('transactions/<uuid:uuid>/delete/', views.transaction_delete, name='transaction_delete'),
    path('reports/book/', views.report_cashbank_book, name='report_cashbank_book'),
]