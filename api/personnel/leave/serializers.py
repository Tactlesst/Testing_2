from rest_framework import serializers

from backend.leave.models import LeaveCertificationTransaction
from backend.libraries.leave.models import LeaveApplication, CTDORequests, CTDOBalance
from backend.libraries.leave.models import LeaveSignatories,LeaveCompenattachment
from django.conf import settings
import hashlib


# class LeaveSerializer(serializers.ModelSerializer):
#     leavesubtype_name = serializers.CharField(source='leavesubtype.name', read_only=True)
#     requested_by = serializers.CharField(source='emp.pi.user.get_fullname', read_only=True)
#     inclusive_dates = serializers.CharField(source='get_inclusive', read_only=True, allow_null=True)
#     date_of_filing = serializers.DateTimeField(format="%Y-%m-%d %H:%M %p", read_only=True)
#     approved_date = serializers.DateTimeField(format="%b %d, %Y %H:%M %p", read_only=True)
#     file_name = serializers.CharField(source='file.name', read_only=True, allow_null=True)
#     status = serializers.CharField()

#     class Meta:
#         model = LeaveApplication
#         fields = [
#             'id',
#             'tracking_no',
#             'leavesubtype_name',
#             'inclusive_dates',
#             'start_date',
#             'end_date',
#             'date_of_filing',
#             'status',
#             'requested_by',
#             'approved_date',
#             'file_name',
#             'get_status',
#         ]

#     def get_get_file_status(self, obj):
#         return obj.get_file_status


class LeaveSerializer(serializers.ModelSerializer):
    leavesubtype_name = serializers.CharField(source='leavesubtype.name', read_only=True)
    requested_by = serializers.CharField(source='emp.pi.user.get_fullname', read_only=True)
    inclusive_dates = serializers.CharField(source='get_inclusive', read_only=True, allow_null=True)
    date_of_filing = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    approved_date = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    file_name = serializers.CharField(source='file.name', read_only=True, allow_null=True)
    status = serializers.CharField()
    fundsource = serializers.CharField(source='emp.fundsource.name', read_only=True)
    section = serializers.CharField(source='emp.section.sec_acronym',read_only=True)
    action = serializers.CharField(source='get_action', read_only=True)  

    class Meta:
        model = LeaveApplication
        fields = [
            'id', 'tracking_no', 'leavesubtype_name', 'inclusive_dates',
            'start_date', 'end_date', 'date_of_filing',
            'status', 'requested_by', 'approved_date',
            'file_name', 'get_status','fundsource','section','action',
        ]
        


class CTDOSerializer(serializers.ModelSerializer):
    inclusive_dates = serializers.CharField(source='get_inclusive', read_only=True)
    requested_by = serializers.CharField(source='emp.pi.user.get_fullname', read_only=True)
    date_filed = serializers.DateTimeField(format="%b %d, %Y %H:%M %p", read_only=True)

    class Meta:
        model = CTDORequests
        fields = ['id', 'tracking_no', 'inclusive_dates', 'date_filed', 'status', 'requested_by']


class LeaveCertificationTransactionSerializer(serializers.ModelSerializer):
    date_created = serializers.DateTimeField(format="%b %d, %Y %H:%M %p", read_only=True)
    created_by = serializers.CharField(source='created_by.pi.user.get_fullname', read_only=True)
    type = serializers.CharField(source='type.name', read_only=True)

    class Meta:
        model = LeaveCertificationTransaction
        fields = ['id', 'drn', 'date_created', 'created_by', 'title', 'type', 'emp_id']


class CTDOBalanceSerializer(serializers.ModelSerializer):
    date_expiry = serializers.DateField(format="%b %d, %Y", read_only=True)

    class Meta:
        model = CTDOBalance
        fields = ['id', 'days', 'hours', 'minutes', 'date_expiry', 'month_earned', 'status']
        
        


    
class LeaveForApprovalSerializer(serializers.ModelSerializer):
    
    leave_id = serializers.CharField(source='leave.id', read_only=True)
    tracking_no = serializers.CharField(source='leave.tracking_no', read_only=True)
    leavesubtype_name = serializers.CharField(source='leave.leavesubtype.name', read_only=True)
    date_of_filing = serializers.DateTimeField(source='leave.date_of_filing',format="%Y-%m-%d %I:%M %p", read_only=True)
    get_status = serializers.CharField(source='leave.get_status',read_only=True)
    action = serializers.CharField(source='leave.get_action', read_only=True)
    requested_by = serializers.CharField(source='leave.emp.pi.user.get_fullname', read_only=True)
    inclusive_date = serializers.CharField(source ='leave.get_inclusive', read_only = True)
    
    
    class Meta:
        model = LeaveSignatories
        fields = ['id', 'leave_id', 'tracking_no','leavesubtype_name','date_of_filing','status','get_status','action',
                  'requested_by','inclusive_date']

    def get_hashed_id(self, obj):
        secret = settings.SECRET_KEY
        raw = f"{obj.id}{secret}"
        return hashlib.sha256(raw.encode()).hexdigest()

class LeaveCompensatorySerializer(serializers.ModelSerializer):
    file = serializers.FileField(source="file_attachement", required=True)
    requester_name = serializers.CharField(source="requester.pi.user.get_fullname", read_only=True)
    uploaded_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    action = serializers.CharField(source='get_action',read_only = True)
    status = serializers.CharField(source='get_status',read_only=True)
    tracking_number = serializers.CharField(source='compen_tracking', read_only=True)
    admin_remarks =serializers.CharField(source='remarks',read_only = True)
    approved_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)


    class Meta:
        model = LeaveCompenattachment
        fields = ['id', 'file','uploaded_at','requester_name','action','status','tracking_number','admin_remarks','approved_date']
        
        
class AdminLeaveCompensatorySerializer(serializers.ModelSerializer):
    file = serializers.FileField(source="file_attachement", required=False)
    requester_name = serializers.CharField(source="requester.pi.user.get_fullname", read_only=True)
    uploaded_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    admin_action = serializers.CharField(source='get_admin_action', read_only=True) 
    status = serializers.CharField(source='get_status', read_only=True)
    tracking_number = serializers.CharField(source='compen_tracking', read_only=True)
    fund_source = serializers.CharField(source='requester.fundsource.name',read_only=True)
    aoa = serializers.CharField(source='requester.aoa.name',read_only=True)
    admin_remarks =serializers.CharField(source='remarks',read_only = True)
    approved_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M", required=False)



    class Meta:
        model = LeaveCompenattachment
        fields = ['id', 'file', 'uploaded_at', 'requester_name', 'admin_action', 'status', 'tracking_number','fund_source','aoa','admin_remarks','approved_date']

