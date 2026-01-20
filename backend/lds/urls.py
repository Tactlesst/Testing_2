from django.urls import path
from . import views
from backend.lds.views import ld_admin, generate_drn_for_rso, bypass_lds_rso_approval, \
    bypass_lds_rrso_approval

urlpatterns = [
    path('', ld_admin, name='ld_admin'),
    #added paths for LDI plan by Nazef
    path('ld-list/', views.ldi_list, name='ldi_list'),
    path('ld-list/ajax/', views.ldi_list_ajax, name='ldi_list_ajax'),
    path('ld-plan/get/<int:pk>/', views.ldi_plan_get, name='ldi_plan_get'),
    path('ld-plan/get-by-training/<int:training_id>/', views.ldi_plan_get_by_training, name='ldi_plan_get_by_training'),
    path('ld-plan/details/<int:training_id>/', views.ldi_plan_details, name='ldi_plan_details'),
    path('ld-plan/save/', views.ldi_plan_save, name='ldi_plan_save'),
    path('ld-plan/delete/<int:pk>/', views.ldi_plan_delete, name='ldi_plan_delete'),
    path('ld-plan/', views.ldi_plan, name='ldi_plan_new'),  # Create new
    path('ld-plan/<str:plan_id>/', views.ldi_plan, name='ldi_plan'),  # Edit 

    # nazef working in this code start
    path('training-list/', views.lds_training_list, name='lds_training_list'),
    path('training-list/ajax/', views.lds_training_list_ajax, name='lds_training_list_ajax'),
    path('training-list/ajax/<int:training_id>/', views.lds_training_list_details_ajax, name='lds_training_list_details_ajax'),
    path('training-list/details/<int:training_id>/', views.lds_training_list_details, name='lds_training_list_details'),
    path('training-list/participants/<int:rso_id>/', views.lds_training_list_participants, name='lds_training_list_participants'),
    path('training-list/search/', views.lds_training_list_search, name='lds_training_list_search'),
    path('training-list/create/', views.lds_training_list_create, name='lds_training_list_create'),
    path('training-list/update/<int:training_id>/', views.lds_training_title_update, name='lds_training_title_update'),
    path('training-list/delete/<int:training_id>/', views.lds_training_title_delete, name='lds_training_title_delete'),
    # nazef working in this code end
    #end added paths for LDI plan by Nazef

    path('rrso/bypass-approval/<int:pk>', bypass_lds_rrso_approval, name='bypass_lds_rrso_approval'),
    path('rso/bypass-approval/<int:pk>', bypass_lds_rso_approval, name='bypass_lds_rso_approval'),
    path('generate/rso/', generate_drn_for_rso, name='generate_drn_for_rso'),
]