from django.urls import path
from . import views
from backend.lds.views import ld_admin, generate_drn_for_rso, bypass_lds_rso_approval, \
    bypass_lds_rrso_approval

urlpatterns = [
    path('', ld_admin, name='ld_admin'),
    #added paths for LDI plan by Nazef
    path('ld-list/', views.ldi_list, name='ldi_list'),
    path('ld-plan/', views.ldi_plan, name='ldi_plan_new'),  # Create new
    path('ld-plan/<str:plan_id>/', views.ldi_plan, name='ldi_plan'),  # Edit existing
    #end added paths for LDI plan by Nazef
    path('rrso/bypass-approval/<int:pk>', bypass_lds_rrso_approval, name='bypass_lds_rrso_approval'),
    path('rso/bypass-approval/<int:pk>', bypass_lds_rso_approval, name='bypass_lds_rso_approval'),
    path('generate/rso/', generate_drn_for_rso, name='generate_drn_for_rso'),
]