from django.db.models.functions import Upper
from django.db.models import Q
from django_mysql.models.functions import SHA1
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated

from api.personnel.employees.serializers import WorkExperienceSerializer, EmployeeAdminSerializer, SectionSerializer, \
    IPCRSerializer, ServiceRecordSerializer, PositionVacancySerializer, JobApplicationSerializer,SectionHeadSerializer
from backend.ipcr.models import IPC_Rating
from backend.models import Empprofile, Section, PositionVacancy
from backend.pas.service_record.models import PasServiceRecord
from backend.templatetags.tags import check_permission
from frontend.models import Workhistory
from landing.models import JobApplication
from django.db.models import Value, CharField
from django.db.models.functions import Concat
from django.db import models



class WorkExperienceViews(generics.ListAPIView):
    serializer_class = WorkExperienceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Workhistory.objects.annotate(hash=SHA1('emp_id'), we_to=Upper('we__we_to')).filter(hash=self.request.query_params.get('employee_id'))

        return queryset


class EmployeePermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'employee_list') or check_permission(request.user, 'superadmin') :
            return True
        else:
            return False


class PerformanceManagerPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'performance_manager') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


class PositionPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'position') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


class RecruitmentPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'recruitment') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


class EmployeeAdminViews(generics.ListAPIView):
    serializer_class = EmployeeAdminSerializer
    permission_classes = [IsAuthenticated, EmployeePermissions]

    def get_queryset(self):
        position_id = self.request.query_params.get('position')
        section_id = self.request.query_params.get('section')
        aoa_id = self.request.query_params.get('aoa') 
        fundsource_id = self.request.query_params.get('fundsource')
        empstatus_id = self.request.query_params.get('empstatus')
        division_id = self.request.query_params.get('division')
        gender_id = self.request.query_params.get('gender')  
        designation = self.request.query_params.get('designation')  


        queryset = Empprofile.objects.order_by('pi__user__last_name')

        print("POSITION ID: ", position_id)
        if position_id:
            queryset = queryset.filter(position_id=position_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        if aoa_id:
            queryset = queryset.filter(aoa_id=aoa_id)  
        if fundsource_id:
            queryset = queryset.filter(fundsource_id=fundsource_id)  
        if empstatus_id:
            queryset = queryset.filter(empstatus_id=empstatus_id)  
        if division_id:
            queryset = queryset.filter(section__div_id=division_id)
        if gender_id:
            queryset = queryset.filter(pi__gender=gender_id)
        if designation:
            queryset = queryset.filter(designation__icontains=designation)  

        return queryset


class SectionViews(generics.ListAPIView):
    queryset = Section.objects.all().order_by('sec_name')
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated]

class IPCRViews(generics.ListAPIView):
    serializer_class = IPCRSerializer
    permission_classes = [IsAuthenticated, PerformanceManagerPermissions]

    def get_queryset(self):
        queryset = IPC_Rating.objects.annotate(
            full_name=Concat(
                'emp__pi__user__last_name', Value(', '),
                'emp__pi__user__first_name', Value(' '),
                'emp__pi__user__middle_name',
                output_field=CharField()
            )
        ).order_by('-date_added')

        year = self.request.query_params.get('year', None)
        semester = self.request.query_params.get('semester', None)

        if year:
            queryset = queryset.filter(year=year)
        if semester:
            queryset = queryset.filter(semester=semester)

        return queryset


class IPCRDivisionViews(generics.ListAPIView):
    serializer_class = IPCRSerializer
    permissions_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = IPC_Rating.objects.annotate(hash_pk=SHA1('emp__section__div_id')).filter(hash_pk=self.request.query_params.get('pk')).order_by('-date_added')
        return queryset


class IPCREmpViews(generics.ListAPIView):
    serializer_class = IPCRSerializer
    permissions_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = IPC_Rating.objects.annotate(hash_pk=SHA1('emp__id')).filter(hash_pk=self.request.query_params.get('pk')).order_by('-date_added')
        return queryset


# class ServiceRecordViews(generics.ListAPIView):
#     serializer_class = ServiceRecordSerializer
#     permissions_classes = [IsAuthenticated]

#     def get_queryset(self):
#         queryset = PasServiceRecord.objects.annotate(hash=SHA1('emp_id')).filter(
#             hash=self.request.query_params.get('pk'),
#             status=1
#         )

#         return queryset


class ServiceRecordViews(generics.ListAPIView):
    serializer_class = ServiceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        emp_id = self.request.query_params.get('pk')

        print(f"Searching for emp_id: {emp_id}")

        if not emp_id:
            return PasServiceRecord.objects.none() 

        queryset = PasServiceRecord.objects.filter(
            emp_id=emp_id,  # Filter by emp_id
        )
        
        print(f"Filtered records: {queryset}")
        
        return queryset



class PositionVacancyViews(generics.ListAPIView):
    serializer_class = PositionVacancySerializer
    permission_classes = [IsAuthenticated, PositionPermissions]

    def get_queryset(self):
        status = self.request.query_params.get('status')
        if status == "drafts":
            queryset = PositionVacancy.objects.filter(status=0, upload_by_id=self.request.session['user_id'])
            return queryset
        elif status == "vacancy":
            queryset = PositionVacancy.objects.filter(status=1)
            return queryset
        elif status == "filled":
            queryset = PositionVacancy.objects.filter(status=2)
            return queryset


class JobApplicationViews(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, RecruitmentPermissions]

    def get_queryset(self):
        status = self.request.query_params.get('status', '')

        if status == "reject":
            queryset = JobApplication.objects.filter(is_rejected=1)
            return queryset
        elif status != "":
            queryset = JobApplication.objects.filter(
                Q(app_status_id=status), Q(is_rejected=0) | Q(is_rejected__isnull=True)
            )
            return queryset
        else:
            queryset = JobApplication.objects.all()
            return queryset


class SectionHeadViews(generics.ListAPIView):
    serializer_class = SectionHeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        section_id = self.request.query_params.get('section_id')
        queryset = Empprofile.objects.all()
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        return queryset.filter(id=models.F('section__sec_head_id'))