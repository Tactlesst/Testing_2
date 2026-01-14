from django.urls import path

from backend.pas.transmittal.views import transmittal, view_transmittal, delete_transmittal, view_transmittal_details, \
    add_employee_transmittal,update_transmittal_details

urlpatterns = [
    path('', transmittal, name='transmittal'),
    path('add/employee/<int:type>', add_employee_transmittal, name='add_employee_transmittal'),
    path('delete/', delete_transmittal, name='delete_transmittal'),
    path('view/<str:pk>', view_transmittal, name='view_transmittal'),
    path('view/details/<int:pk>', view_transmittal_details, name='view_transmittal_details'),
    path('update/details/<int:pk>', update_transmittal_details, name='update_transmittal_details')
]