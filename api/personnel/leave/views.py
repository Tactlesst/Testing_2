from django_mysql.models.functions import SHA1
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated

from api.personnel.leave.serializers import LeaveSerializer, CTDOSerializer, LeaveCertificationTransactionSerializer, \
    CTDOBalanceSerializer,LeaveForApprovalSerializer,AdminLeaveCompensatorySerializer,LeaveCompensatorySerializer
from backend.leave.models import LeaveCertificationTransaction
from backend.libraries.leave.models import LeaveApplication, CTDORequests, CTDOBalance,LeaveCompenattachment,LeaveSignatories
from backend.templatetags.tags import check_permission
from django.db.models import Q, OuterRef, Exists
from backend.models import Section,Empprofile



class LeaveAdminPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'leave') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


class LeaveViews(generics.ListAPIView):
    serializer_class = LeaveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.query_params.get('status'):
            queryset = LeaveApplication.objects.annotate(hash=SHA1('emp_id')).filter(
                hash=self.request.query_params.get('employee_id'),
                status=self.request.query_params.get('status')
            )
            return queryset
        else:
            queryset = LeaveApplication.objects.annotate(hash=SHA1('emp_id')).filter(hash=self.request.query_params.get('employee_id'))
            return queryset


# class LeaveAdminViews(generics.ListAPIView):
#     serializer_class = LeaveSerializer
#     permission_classes = [IsAuthenticated, LeaveAdminPermissions]

#     def get_queryset(self):
#         if self.request.query_params.get('status'):
#             queryset = LeaveApplication.objects.filter(
#                 date_of_filing__year=self.request.query_params.get('year'),
#                 status=self.request.query_params.get('status')
#             )
#             return queryset
#         else:
#             queryset = ''
#             if self.request.query_params.get('year'):
#                 queryset = LeaveApplication.objects.filter(date_of_filing__year=self.request.query_params.get('year'))
#             else:
#                 queryset = LeaveApplication.objects.all()

#             return queryset

class LeaveAdminViews(generics.ListAPIView):
    serializer_class = LeaveSerializer
    permission_classes = [IsAuthenticated, LeaveAdminPermissions]

    def get_queryset(self):
        year = self.request.query_params.get('year')
        status = self.request.query_params.get('status')
        fundsource = self.request.query_params.get('fundsource') 
        queryset = LeaveApplication.objects.all()

        if year:
            queryset = queryset.filter(date_of_filing__year=year)

        if status is not None:
            queryset = queryset.filter(status=status)

        if fundsource:  
            queryset = queryset.filter(emp__fundsource_id=fundsource)  

        # hr_pas_head_section = Section.objects.filter(sec_name='Personnel Administration').first()
        # if hr_pas_head_section and hr_pas_head_section.sec_head_id:
        #     hr_pas_head_emp_id = hr_pas_head_section.sec_head_id

        #     queryset = queryset.filter(
        #         leavesignatories__emp_id=hr_pas_head_emp_id,
        #         leavesignatories__status=1
        #     ).distinct()

        return queryset


class CTDOViews(generics.ListAPIView):
    serializer_class = CTDOSerializer
    permissions_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.query_params.get('status'):
            queryset = CTDORequests.objects.annotate(hash=SHA1('emp_id')).filter(
                hash=self.request.query_params.get('employee_id'),
                status=self.request.query_params.get('status')
            )
            return queryset
        else:
            queryset = CTDORequests.objects.annotate(hash=SHA1('emp_id')).filter(hash=self.request.query_params.get('employee_id'))
            return queryset


class CTDOAdminViews(generics.ListAPIView):
    serializer_class = CTDOSerializer
    permissions_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.query_params.get('status'):
            queryset = CTDORequests.objects.filter(
                status=self.request.query_params.get('status')
            )
            return queryset
        else:
            queryset = CTDORequests.objects.order_by('-tracking_no')
            return queryset


class LeaveCertificationTransactionViews(generics.ListAPIView):
    serializer_class = LeaveCertificationTransactionSerializer
    permissions_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LeaveCertificationTransaction.objects.filter(
            emp_id=self.request.query_params.get('employee_id'), status=1
        )
        return queryset


class CTDOBalanceViews(generics.ListAPIView):
    serializer_class = CTDOBalanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CTDOBalance.objects.filter(emp_id=self.request.query_params.get('emp_id'))
        return queryset
    
    


class LeaveForApprovalView(generics.ListAPIView):
    serializer_class = LeaveForApprovalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        employee_id = self.request.query_params.get('employee_id')

        base = LeaveSignatories.objects.filter(
            emp_id=employee_id,
            status=0  
        ).select_related('leave', 'leave__leavesubtype', 'emp__pi__user')

        prev_pending = LeaveSignatories.objects.filter(
            leave_id=OuterRef('leave_id'),
            signatory_type__lt=OuterRef('signatory_type'),
            status=0
        )

        status_disapproved = LeaveSignatories.objects.filter(
            leave_id=OuterRef('leave_id'),
            status=2
        )

        return base.annotate(
            can_approve=~Exists(prev_pending),
            status_disapproved=Exists(status_disapproved),
        ).filter(
            Q(signatory_type=0) | Q(can_approve=True),
            status_disapproved=False  
        )
        
class LeaveCompenAttachmentList(generics.ListAPIView):
    serializer_class = LeaveCompensatorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        emp = Empprofile.objects.filter(pi__user_id=self.request.user.id).first()
        if not emp:
            return LeaveCompenattachment.objects.none()

        return LeaveCompenattachment.objects.filter(requester=emp).order_by('-uploaded_at')

class AdminLeaveCompenAttachmentList(generics.ListAPIView):
    serializer_class = AdminLeaveCompensatorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LeaveCompenattachment.objects.filter(status__in=[1, 2]).order_by('-uploaded_at')


