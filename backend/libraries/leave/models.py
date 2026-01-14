import os
import hashlib, uuid
from django.db import models
from django.dispatch import receiver
from django.utils import timezone
from django.contrib import admin
from datetime import datetime
from backend.models import Empprofile, Empstatus
from portal.global_variables import count_leave_days
from django.db.models import Max
from datetime import datetime
from django.contrib.auth.models import User



class LeaveType(models.Model):
    name = models.CharField(max_length=250)
    status = models.IntegerField(blank=True, null=True)

    @admin.display(boolean=True, description='Status')
    def display_status(self):
        return self.status == 1

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Leave Type'
        managed = False
        db_table = 'leave_type'


class LeaveSubtype(models.Model):
    name = models.CharField(max_length=250)
    description = models.TextField()
    leavetype = models.ForeignKey(LeaveType, models.DO_NOTHING, verbose_name="Leave Type", blank=True, null=True)
    is_others = models.BooleanField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, blank=True, null=True)
    has_reason = models.BooleanField(blank=True, null=True)
    with_days = models.BooleanField(blank=True, null=True)
    remarks_text = models.CharField(max_length=255, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    @admin.display(boolean=True, description='Status')
    def display_status(self):
        return self.status == 1

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Leave Sub-Type'
        managed = False
        db_table = 'leave_subtype'


class LeaveSpent(models.Model):
    name = models.CharField(max_length=250)
    leavesubtype = models.ForeignKey(LeaveSubtype, models.DO_NOTHING, verbose_name="Leave Sub-Type")
    status = models.IntegerField(blank=True, null=True)
    is_specify = models.IntegerField(blank=True, null=True)

    @admin.display(boolean=True, description='Status')
    def display_status(self):
        return self.status == 1

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Leave Spent'
        verbose_name_plural = 'Leave Spent'
        managed = False
        db_table = 'leave_spent'


class LeavePrintLogs(models.Model):
    leaveapp = models.ForeignKey(LeaveType, models.DO_NOTHING)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'leave_print_logs'


class LeaveCredits(models.Model):
    leavetype = models.ForeignKey(LeaveType, models.DO_NOTHING)
    leave_total = models.DecimalField(max_digits=15, decimal_places=3, blank=True, null=True)
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    updated_on = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'leave_credits'


class LeaveCreditHistory(models.Model):
    deduct_on = models.ForeignKey(LeaveType, models.DO_NOTHING)
    days = models.CharField(max_length=255, blank=True, null=True)
    application = models.ForeignKey('LeaveApplication', models.DO_NOTHING)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'leave_credits_history'


# class LeaveApplication(models.Model):
#     tracking_no = models.CharField(max_length=255, blank=True, null=True, unique=True)
#     leavesubtype = models.ForeignKey(LeaveSubtype, models.DO_NOTHING)
#     start_date = models.DateField(blank=True, null=True)
#     end_date = models.DateField(blank=True, null=True)
#     reasons = models.TextField(blank=True, null=True)
#     date_of_filing = models.DateTimeField(blank=True, null=True)
#     status = models.IntegerField(blank=True, null=True)
#     remarks = models.TextField(blank=True, null=True)
#     emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
#     approved_date = models.DateTimeField()
#     additional_remarks = models.TextField(blank=True, null=True)
#     file = models.FileField(blank=True, null=True, upload_to='leave', default='leave/default.pdf')


#     def get_latest_tracker_status(self):
#         from tracker.models import TrackerPackageItem, TrackerPackageItemHistory
#         package = TrackerPackageItem.objects.filter(leave_tracking_no=self.tracking_no)
#         if package:
#             data = TrackerPackageItemHistory.objects.filter(package_id=package.first().id).order_by('-id')
#             if data:
#                 return data.first().status.name
#         else:
#             return 'Pending'

#     def get_inclusive(self):
#         if self.start_date:
#             if self.start_date == self.end_date:
#                 return self.start_date.strftime("%B %d, %Y")
#             else:
#                 if not self.end_date:
#                     return "{}".format(self.start_date.strftime("%B %d, %Y"))
#                 else:
#                     return "{} - {}".format(self.start_date.strftime("%B %d, %Y"), self.end_date.strftime("%B %d, %Y"))
#         else:
#             leave_dates = LeaveRandomDates.objects.filter(leaveapp_id=self.id)
#             if leave_dates:
#                 if leave_dates.count() != 1:
#                     random_dates = []
#                     for row in leave_dates:
#                         random_dates.append(row.date.strftime("%B %d, %Y"))

#                     text = "{} and {}".format(", ".join(str(row) for row in random_dates[:-1]), random_dates[-1])
#                     return text
#                 else:
#                     random_dates = []
#                     for row in leave_dates:
#                         random_dates.append(row.date.strftime("%B %d, %Y"))

#                     text = "{}".format(random_dates[0])
#                     return text
#             else:
#                 return self.remarks

#     def get_leave_delays(self):
#         content = ""
#         days = 0
#         if self.start_date:
#             days = count_leave_days(self.date_of_filing, self.start_date)
#         else:
#             leave_dates = LeaveRandomDates.objects.filter(leaveapp_id=self.id)
#             if leave_dates:
#                 random_dates = []
#                 for row in leave_dates:
#                     random_dates.append(row.date)

#                 days = count_leave_days(self.date_of_filing, random_dates[0])

#         if days > 1:
#             content += '<span class="badge bg-warning">delayed for {} days</span>'.format(days)
#         elif days == 1:
#             content += '<span class="badge bg-warning">delayed for {} day</span>'.format(days)
#         else:
#             content += ''

#         return content
    
#     @property
#     def get_status(self):
#         status_badge = ""
#         if self.status == 0:
#             status_badge = "<span class='badge badge-primary'>Pending</span>"
#         elif self.status == 1:
#             status_badge = "<span class='badge badge-success'>Approved</span>"
#         elif self.status == 2:
#             status_badge = "<span class='badge badge-warning'>Cancelled</span>"
#         else:
#             status_badge = "<span class='badge badge-danger'>Disapproved</span>"
            
#         if self.file and self.file.name != 'leave/default.pdf':
#             file_badge = "<span class='badge badge-success'>File</span>"
#         else:
#             file_badge = "<span class='badge badge-default'>No File</span>"


#         return f"{status_badge} | {file_badge}"


#     class Meta:
#         db_table = 'leave_application'



class LeaveApplication(models.Model):
    tracking_no = models.CharField(max_length=255, blank=True, null=True, unique=True)
    leavesubtype = models.ForeignKey(LeaveSubtype, models.DO_NOTHING)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    reasons = models.TextField(blank=True, null=True)
    date_of_filing = models.DateTimeField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    approved_date = models.DateTimeField()
    additional_remarks = models.TextField(blank=True, null=True)
    file = models.FileField(blank=True, null=True, upload_to='leave', default='leave/default.pdf')

   

    def get_leave_approver(self):
        from backend.libraries.leave.models import LeaveSignatories
        check = LeaveSignatories.objects.filter(leave_id=self.id, status=1)

        if check:
            return check.first().supervisor.pi.user.get_fullname
        else:
            return ''

    def get_latest_tracker_status(self):
        from tracker.models import TrackerPackageItem, TrackerPackageItemHistory
        package = TrackerPackageItem.objects.filter(leave_tracking_no=self.tracking_no)
        if package:
            data = TrackerPackageItemHistory.objects.filter(package_id=package.first().id).order_by('-id')
            if data:
                return data.first().status.name
        else:
            return 'Pending'
        

    def get_inclusive(self):
        if self.start_date:
            if self.start_date == self.end_date:
                return self.start_date.strftime("%B %d, %Y")
            else:
                if not self.end_date:
                    return "{}".format(self.start_date.strftime("%B %d, %Y"))
                else:
                    return "{} - {}".format(self.start_date.strftime("%B %d, %Y"), self.end_date.strftime("%B %d, %Y"))
        else:
            leave_dates = LeaveRandomDates.objects.filter(leaveapp_id=self.id)
            if leave_dates:
                if leave_dates.count() != 1:
                    random_dates = []
                    for row in leave_dates:
                        random_dates.append(row.date.strftime("%B %d, %Y"))

                    text = "{} and {}".format(", ".join(str(row) for row in random_dates[:-1]), random_dates[-1])
                    return text
                else:
                    random_dates = []
                    for row in leave_dates:
                        random_dates.append(row.date.strftime("%B %d, %Y"))

                    text = "{}".format(random_dates[0])
                    return text
            else:
                return self.remarks

    def get_leave_delays(self):
        content = ""
        days = 0
        if self.start_date:
            days = count_leave_days(self.date_of_filing, self.start_date)
        else:
            leave_dates = LeaveRandomDates.objects.filter(leaveapp_id=self.id)
            if leave_dates:
                random_dates = []
                for row in leave_dates:
                    random_dates.append(row.date)

                days = count_leave_days(self.date_of_filing, random_dates[0])

        if days > 1:
            content += '<span class="badge bg-warning">delayed for {} days</span>'.format(days)
        elif days == 1:
            content += '<span class="badge bg-warning">delayed for {} day</span>'.format(days)
        else:
            content += ''

        return content

    
    @property
    def get_action(self):
        action_parts = []

        details_link = f"<a href='/leave/requests/print/{self.id}' target='_blank'>Details</a>"
        action_parts.append(details_link)

        if "Pending" in self.get_status:
            action_parts.append(f"<a href='javascript:void(0)' data-role='edit' data-id='{self.id}' data-filter='{self.tracking_no}'>Edit</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='cancel-leave' data-id='{self.id}'>Cancel</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='set-signatories' data-id='{self.id}'>Signatories</a>")
            
        elif self.get_status == 2:
            action_parts.append(f"<a href='javascript:void(0)' data-role='cancel-leave' data-id='{self.id}'>Cancel</a>")

        elif "Approved" in self.get_status:
            action_parts.append(f"<a href='javascript:void(0)' data-role='attachment' data-id='{self.id}'>Attachment</a>")

        return " | ".join(action_parts)

    @property
    def get_status(self):
        from backend.libraries.leave.models import LeaveSignatories
        if LeaveSignatories.objects.filter(leave_id=self.id, status=2).exists():
            return "<span class='badge badge-danger'>Disapproved</span>"

        if self.status == 0:
            return "<span class='badge badge-primary'>Pending</span>"
        elif self.status == 1:
            return "<span class='badge badge-success'>Approved</span>"
        elif self.status == 2:
            return "<span class='badge badge-warning'>Cancelled</span>"
        elif self.status == 3:
            return "<span class='badge badge-danger'>Disapproved</span>"
        else:
            return "<span class='badge badge-primary'>set signatories</span>"
   
    @property
    def get_subtype(self):
        if self.leavesubtype_id == 7 and (not self.file or self.file.name == 'leave/default.pdf'):
            return False
        return True
    

    class Meta:
        db_table = 'leave_application'
        
        
class LeaveCompenattachment(models.Model):
    compen_tracking = models.CharField(max_length=255, blank=True, null=True, unique=True)
    file_attachement = models.FileField(upload_to="compen_attachment")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    requester = models.ForeignKey(Empprofile, on_delete=models.CASCADE)
    status = models.IntegerField(default=0) 
    remarks = models.CharField(max_length=255,null=True,blank= True)
    approved_date = models.DateTimeField(null=True,blank=True)
    
    
    def save(self, *args, **kwargs):
        if self.status == 2 and self.approved_date is None:
            self.approved_date = timezone.now()

        if not self.compen_tracking:
            self.compen_tracking = self.generate_tracking_number()

        super().save(*args, **kwargs)
    
    def generate_tracking_number(self):
        now = datetime.now()
        year = now.year
        month = str(now.month).zfill(2)
        
        current_month_requests = LeaveCompenattachment.objects.filter(
            uploaded_at__year=year,
            uploaded_at__month=now.month
        ).aggregate(max_id=Max('id'))['max_id']
        
        next_number = 1 if current_month_requests is None else current_month_requests + 1
        
        tracking_number = f"LVC-{year}-{month}-{str(next_number).zfill(4)}"
        
        while LeaveCompenattachment.objects.filter(compen_tracking=tracking_number).exists():
            next_number += 1
            tracking_number = f"LVC-{year}-{month}-{str(next_number).zfill(4)}"
        
        return tracking_number
    
    @property
    def get_action(self):
        action_parts = []
        
        if self.status == 0:
            action_parts.append(f"<a href='javascript:void(0)' data-role='submit' data-id='{self.id}'>Submit</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='cancel-compen' data-id='{self.id}'>Cancel</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")

        elif self.status == 1: 
            action_parts.append(f"<a href='javascript:void(0)' data-role='cancel-compen' data-id='{self.id}'>Cancel</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")

        elif self.status == 2:  
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")
            
        elif self.status == 3:
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")
            
        elif self.status == 4:
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")

        return " | ".join(action_parts)

    
    @property
    def get_admin_action(self):
        action_parts = []
        
        if self.status == 0:
            action_parts.append(f"<a href='javascript:void(0)' data-role='submit' data-id='{self.id}'>Submit</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='cancel-compen' data-id='{self.id}'>Cancel</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='remarks' data-id='{self.id}'>Remarks</a>")
        
        elif self.status == 1:
            action_parts.append(f"<a href='javascript:void(0)' data-role='approve' data-id='{self.id}'>Approve</a>")
            action_parts.append(f"<a href='javascript:void(0)' data-role='reject' data-id='{self.id}'>Reject</a>")
        
        elif self.status == 2:
            action_parts.append(f"<a href='javascript:void(0)' data-role='delete' data-id='{self.id}'>Delete</a>")

        return " | ".join(action_parts)
    
    @property
    def get_status(self):
        if self.status == 0:
            return "<span class='badge badge-info'>Draft</span>"
        elif self.status == 1:
            return "<span class='badge badge-primary'>Pending</span>"
        elif self.status == 2:
            return "<span class='badge badge-success'>Approved</span>"
        elif self.status == 3:
            return "<span class='badge badge-warning'>Cancelled</span>"
        elif self.status == 4:
            return "<span class='badge badge-danger'>Rejected</span>"
        else:
            return "<span class='badge badge-secondary'>Uknown Status</span>"
    
    class Meta:
        db_table = 'leave_compensatory'
    

@receiver(models.signals.pre_save, sender=LeaveApplication)
def auto_delete_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_file = LeaveApplication.objects.get(pk=instance.pk).file
    except LeaveApplication.DoesNotExist:
        return False

    new_file = instance.file
    if not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


class LeavespentApplication(models.Model):
    leaveapp = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE)
    leavespent = models.ForeignKey(LeaveSpent, models.DO_NOTHING, blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    specify = models.TextField(blank=True, null=True)

    def get_start_date(self):
        if self.leaveapp.start_date:
            return self.leaveapp.start_date

    def get_random_dates(self):
        random_dates = LeaveRandomDates.objects.values_list('date', flat=True).filter(leaveapp_id=self.leaveapp_id)
        return random_dates

    def get_leave_status(self):
        if self.leaveapp.status == 0:
            return "Pending"
        elif self.leaveapp.status == 1:
            return "Approved"
        elif self.leaveapp.status == 2:
            return "Cancel"

    def get_leave_reasons(self):
        if self.leaveapp.reasons:
            return self.leaveapp.reasons
        else:
            return self.specify

    class Meta:
        db_table = 'leavespent_application'


class LeaveRandomDates(models.Model):
    leaveapp = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE)
    date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'leave_random_dates'


class CTDORequests(models.Model):
    tracking_no = models.CharField(max_length=255, blank=True, null=True)
    date_filed = models.DateTimeField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    status = models.IntegerField()
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    drn = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='ctdo', blank=True, null=True, default='ctdo/default.pdf')
    coc_filed = models.DateField(blank=True, null=True)

    def get_latest_tracker_status(self):
        from tracker.models import TrackerPackageItem, TrackerPackageItemHistory
        package = TrackerPackageItem.objects.filter(leave_tracking_no=self.tracking_no)
        if package:
            data = TrackerPackageItemHistory.objects.filter(package_id=package.first().id).order_by('-id')
            if data:
                return data.first().status.name
        else:
            return 'Pending'

    def get_inclusive(self):
        if self.start_date:
            if self.start_date == self.end_date:
                return self.start_date.strftime("%B %d, %Y")
            else:
                if not self.end_date:
                    return "{}".format(self.start_date.strftime("%B %d, %Y"))
                else:
                    return "{} - {}".format(self.start_date.strftime("%B %d, %Y"),
                                            self.end_date.strftime("%B %d, %Y"))
        else:
            ctdo_dates = CTDORandomDates.objects.filter(ctdo_id=self.id)
            if ctdo_dates:
                if ctdo_dates.count() != 1:
                    random_dates = []
                    for row in ctdo_dates:
                        random_dates.append(row.date.strftime("%B %d, %Y"))

                    text = "{} and {}".format(", ".join(str(row) for row in random_dates[:-1]), random_dates[-1])
                    return text
                else:
                    random_dates = []
                    for row in ctdo_dates:
                        random_dates.append(row.date.strftime("%B %d, %Y"))

                    text = "{}".format(random_dates[0])
                    return text

    class Meta:
        db_table = 'ctdo_requests'


@receiver(models.signals.pre_save, sender=CTDORequests)
def auto_delete_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_file = CTDORequests.objects.get(pk=instance.pk).file
    except LeaveApplication.DoesNotExist:
        return False

    new_file = instance.file
    if not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


class CTDOPrintLogs(models.Model):
    ctdo = models.ForeignKey('CTDORequests', models.DO_NOTHING)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'ctdo_print_logs'


class CTDORandomDates(models.Model):
    ctdo = models.ForeignKey('CTDORequests', models.DO_NOTHING)
    date = models.DateField(blank=True, null=True)
    type = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'ctdo_random_dates'


class LeaveSignatory(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    level = models.IntegerField(blank=True, null=True)
    classes = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'leave_signatory'


class LeavePermissions(models.Model):
    leavesubtype = models.ForeignKey(
        LeaveSubtype, models.DO_NOTHING, blank=True, null=True, verbose_name='Leave Sub-Type'
    )
    empstatus_id = models.IntegerField(blank=True, null=True)

    @admin.display(description='Employee status')
    def display_empstatus(self):
        return Empstatus.objects.filter(id=self.empstatus_id).first()

    class Meta:
        managed = False
        verbose_name = 'Leave Permission'
        verbose_name_plural = 'Leave Permissions'
        db_table = 'leave_permissions'


class CTDOBalance(models.Model):
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    days = models.FloatField(blank=True, null=True)
    hours = models.FloatField(blank=True, null=True)
    minutes = models.FloatField(blank=True, null=True)
    date_expiry = models.DateField(blank=True, null=True)
    month_earned = models.CharField(max_length=255, blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ctdo_balance'


class CTDOActualBalance(models.Model):
    cocbal = models.ForeignKey('CTDOBalance', models.DO_NOTHING)
    days = models.FloatField(blank=True, null=True)
    hours = models.FloatField(blank=True, null=True)
    minutes = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ctdo_actual_balance'


class CTDOUtilization(models.Model):
    ctdoreq = models.ForeignKey('CTDORequests', models.DO_NOTHING, blank=True, null=True)
    days = models.FloatField(blank=True, null=True)
    hours = models.FloatField(blank=True, null=True)
    minutes = models.FloatField(blank=True, null=True)
    cocactualbal = models.ForeignKey('CTDOActualBalance', models.DO_NOTHING)
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    status = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'ctdo_utilization'


class CTDOHistoryBalance(models.Model):
    ctdoreq = models.ForeignKey('CTDORequests', models.DO_NOTHING)
    total_days = models.IntegerField(blank=True, null=True)
    total_hours = models.IntegerField(blank=True, null=True)
    total_minutes = models.IntegerField(blank=True, null=True)
    total_u_days = models.IntegerField(blank=True, null=True)
    total_u_hours = models.IntegerField(blank=True, null=True)
    total_u_minutes = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ctdo_history_balance'


class CTDOCoc(models.Model):
    ctdoreq = models.ForeignKey('CTDORequests', models.DO_NOTHING)
    month_earned = models.CharField(max_length=255, blank=True, null=True)
    days = models.IntegerField(blank=True, null=True)
    hours = models.IntegerField(blank=True, null=True)
    minutes = models.IntegerField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'ctdo_coc'
        


def encrypt_filename(instance, filename):
    ext = filename.split('.')[-1]
    salt = f"{instance.emp.pi.user.id}-{uuid.uuid4()}-{datetime.now().timestamp()}"
    hashed = hashlib.sha256(salt.encode()).hexdigest()
    return f"certs/{hashed}.{ext}"
        
        
class Signature(models.Model):
    
    emp = models.ForeignKey(Empprofile, on_delete=models.CASCADE)
    signature_img = models.ImageField(upload_to="signatures/images/", null=True, blank=True)
    p12_file = models.FileField(upload_to=encrypt_filename, null=True, blank=True) 
    p12_password_enc = models.BinaryField(null=True, blank=True) 
    uploaded = models.DateTimeField(auto_now_add=True)


    class Meta:
            managed = False
            db_table = 'tbl_digsign'

class LeaveSignatories(models.Model):
    id = models.IntegerField(primary_key=True) 
    leave = models.ForeignKey(LeaveApplication,  null=True, on_delete=models.CASCADE)
    emp = models.ForeignKey(Empprofile,  null=True, on_delete=models.CASCADE)
    status = models.IntegerField(default=0)
    signatory_type = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(blank=True, null=True)


    class Meta:
        managed = False
        db_table = 'pas_leave_signatories'