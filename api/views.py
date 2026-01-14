from django.db.models.functions import Upper
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.serializers import PortalConfigSerializer, PermissionSerializer, RestFrameworkTrackingSerializer, \
    UserPermissionSerializer, SMSSerializer, FeedbackSerializer, PatchesSerializer, ConvocationSerializer, \
    PortalSuccessLogsSerializer,UserListSerializer
from api.wiserv import send_notification
from backend.convocation.models import ConvocationEvent
from backend.models import AuthPermission, RestFrameworkTrackingApirequestlog, AuthUserUserPermissions, SMSLogs, \
    Empprofile, Patches, PortalSuccessLogs,Personalinfo
from backend.templatetags.tags import check_permission
from frontend.models import PortalConfiguration, Feedback,AuthUser
from django.contrib.auth import authenticate, login
from rest_framework.views import APIView



class SuperAdminPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_superuser)


class PortalConfigViews(generics.ListAPIView):
    queryset = PortalConfiguration.objects.all().order_by('key_name')
    serializer_class = PortalConfigSerializer
    permission_classes = [IsAuthenticated, SuperAdminPermissions]


class PermissionViews(generics.ListAPIView):
    queryset = AuthPermission.objects.all().order_by('name')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, SuperAdminPermissions]


class UserPermissionViews(generics.ListAPIView):
    serializer_class = UserPermissionSerializer
    permission_classes = [IsAuthenticated, SuperAdminPermissions]

    def get_queryset(self):
        queryset = AuthUserUserPermissions.objects.filter(permission_id=self.request.query_params.get('permission_id')).order_by('user__last_name').annotate(fullname=Upper('user__first_name'))
        return queryset


class RestFrameworkTrackingApirequestlogViews(generics.ListAPIView):
    queryset = RestFrameworkTrackingApirequestlog.objects.order_by('-requested_at')
    serializer_class = RestFrameworkTrackingSerializer
    permission_classes = [IsAuthenticated, SuperAdminPermissions]


class PatchesViews(generics.ListAPIView):
    queryset = Patches.objects.order_by('-release_date')
    serializer_class = PatchesSerializer
    permission_classes = [IsAuthenticated, SuperAdminPermissions]


class SMSPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'text_blast') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_send_sms(request):
    if request.method == "POST":
        employee = Empprofile.objects.filter(id_number=request.query_params.get('id_number')).first()
        send_notification(request.query_params.get('message'), request.query_params.get('number'), employee.id)
        return Response({'msg': 'sent'}, status=status.HTTP_201_CREATED)


class SMSViews(generics.ListAPIView):
    queryset = SMSLogs.objects.all()
    serializer_class = SMSSerializer
    permission_classes = [IsAuthenticated, SMSPermissions]


class SMSUserView(generics.ListAPIView):
    serializer_class = SMSSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        check = SMSLogs.objects.filter(contact_number=self.request.query_params.get('contact_number'))
        if check and not check.first().receiver_id:
            check.update(
                receiver_id=self.request.query_params.get('receiver_id')
            )
        queryset = SMSLogs.objects.filter(receiver_id=self.request.query_params.get('receiver_id'))
        return queryset


class FeedbackViews(generics.ListAPIView):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated, SMSPermissions]


class ConvocationEventViews(generics.ListAPIView):
    queryset = ConvocationEvent.objects.order_by('-date')
    serializer_class = ConvocationSerializer
    permissions_classes = [IsAuthenticated, SuperAdminPermissions]


class PortalSuccessLogsViews(generics.ListAPIView):
    serializer_class = PortalSuccessLogsSerializer

    def get_queryset(self):
        emp_id = self.request.query_params.get('pk')
        type = self.request.query_params.get('type')
        queryset = PortalSuccessLogs.objects.filter(emp_id=emp_id, type=type).order_by('-date_created')

        return queryset



class UserListAPIView(generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AuthUser.objects.filter(is_active=1)
    

class LoginAPIView(APIView):
    def get(self, request):
        return Response({"message": "Please use POST to log in."}, status=200)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            try:
                personal_info = Personalinfo.objects.get(user_id=user.id)
                employee_info = Empprofile.objects.get(pi_id=personal_info.id)

                id_number = employee_info.id_number if employee_info.id_number else None
                position = employee_info.position.name if employee_info.position else None
                section = employee_info.section.sec_name if employee_info.section else None
                division = employee_info.section.div.div_acronym if employee_info.section and employee_info.section.div else None
                mobile_no = personal_info.mobile_no if personal_info.mobile_no else None
                section_id = employee_info.section.id if employee_info.section else None
                division_id = employee_info.section.div.id if employee_info.section and employee_info.section.div else None


            except (Personalinfo.DoesNotExist, Empprofile.DoesNotExist):
                id_number,position, section, division = None, None, None, None

            session_id = request.session.session_key
            response_data = {
                "session_id": session_id,
                "username": user.username,
                "id_number": id_number,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "position": position,  
                "section": section,    
                "division": division,  
                "mobile":mobile_no,
                "section_id":section_id,
                "division_id":division_id,
                "user_type_id": user.user_type_id, 
            }
            return Response(response_data, status=200)

        return Response({"error": "Invalid credentials"}, status=401)