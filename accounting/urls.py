from django.urls import path

from accounting import views

app_name = 'accounting'

urlpatterns = [
    path('accounts/', views.account_list, name='account_list'),
    path('journals/', views.journal_list, name='journal_list'),
    path('journals/new/', views.journal_create, name='journal_create'),
    path('journals/<uuid:uuid>/', views.journal_detail, name='journal_detail'),
    path('journals/<uuid:uuid>/edit/', views.journal_edit, name='journal_edit'),
    path('journals/<uuid:uuid>/post/', views.journal_post, name='journal_post'),
    path('journals/<uuid:uuid>/reverse/', views.journal_reverse, name='journal_reverse'),
    path('periods/', views.period_list, name='period_list'),
    path('periods/<uuid:uuid>/close/', views.period_close, name='period_close'),
    path('modules/', views.module_list, name='module_list'),
    path('reports/general-ledger/', views.report_general_ledger, name='report_general_ledger'),
    path('reports/trial-balance/', views.report_trial_balance, name='report_trial_balance'),
    path('reports/income-statement/', views.report_income_statement, name='report_income_statement'),
    path('reports/balance-sheet/', views.report_balance_sheet, name='report_balance_sheet'),
    path('reports/cash-flow/', views.report_cash_flow, name='report_cash_flow'),
]
