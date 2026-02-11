import os
from django.db import models
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

from backend.models import Empprofile
from frontend.models import Trainingtitle



class LdsTrainingApprovalNotify(models.Model):
    """An Upgrade to the Current Training Notification System"""
    tt_title = models.ForeignKey(Trainingtitle, models.DO_NOTHING, db_column='training_rso', blank=True, null=True)
    approved_by = models.ForeignKey(Empprofile, models.DO_NOTHING, db_column='approved_by', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lds_training_notifications'
        ordering = ['-id']


class LdsCertificateType(models.Model):
    keyword = models.CharField(max_length=255, blank=True, null=True)
    adjective = models.CharField(max_length=255, blank=True, null=True)
    type = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'lds_certificate_type'





class LdsFacilitator(models.Model):
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    rso = models.ForeignKey('LdsRso', on_delete=models.CASCADE)
    is_resource_person = models.IntegerField(blank=True, null=True)
    is_external = models.BooleanField(blank=True, null=True)
    rp_name = models.TextField(blank=True, null=True)
    is_group = models.BooleanField(blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'lds_facilitator'





class LdsParticipants(models.Model):
    emp = models.ForeignKey(Empprofile, models.DO_NOTHING, blank=True, null=True)
    rso = models.ForeignKey('LdsRso', on_delete=models.DO_NOTHING)
    type = models.IntegerField(blank=True, null=True)
    participants_name = models.CharField(max_length=1024, blank=True, null=True)
    is_present = models.IntegerField(blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    @property
    def get_participant_type(self):
        return 'Internal' if self.type == 0 else 'External'

    class Meta:
        db_table = 'lds_participants'





class LdsRso(models.Model):
    training = models.ForeignKey(Trainingtitle, models.CASCADE)
    venue = models.CharField(max_length=1024, blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    quarter = models.CharField(max_length=2, blank=True, null=True)
    rrso_status = models.IntegerField(blank=True, null=True)
    rso_status = models.IntegerField(blank=True, null=True)
    date_approved = models.DateTimeField(blank=True, null=True)
    attachment = models.FileField(upload_to='lds/')
    date_added = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(Empprofile, models.DO_NOTHING)
    is_online_platform = models.IntegerField(blank=True, null=True)

    @property
    def get_inclusive_dates(self):
        if not self.start_date or not self.end_date:
            return ""

        start = self.start_date.date()
        end = self.end_date.date()

        if start != end:
            if start.month == end.month:
                return "{} - {}".format(
                    start.strftime("%B %d"),
                    end.strftime("%d, %Y")
                )

            else:
                return "{} - {}".format(
                    start.strftime("%B %d, %Y"),
                    end.strftime("%B %d, %Y")
                )

        else:
            return start.strftime("%B %d, %Y")

    @property
    def get_inclusive_dates_v2(self):
        if not self.start_date or not self.end_date:
            return ""

        start = self.start_date.date()
        end = self.end_date.date()

        if start != end:
            if start.year == end.year:
                return "{} - {}".format(
                    start.strftime("%B %d"),
                    end.strftime("%B %d, %Y")
                )

            else:
                return "{} - {}".format(
                    start.strftime("%B %d, %Y"),
                    end.strftime("%B %d, %Y")
                )
        else:
            return start.strftime("%B %d, %Y")


    @property
    def training_hours(self):
        if self.start_date and self.end_date:
            days = (self.end_date.date() - self.start_date.date()).days + 1
            return days * 8
        return 0

    @property
    def get_time_range(self):
        if self.start_date and self.end_date:
            return "{} - {}".format(
                self.start_date.strftime("%I:%M %p"),
                self.end_date.strftime("%I:%M %p")
            )
        return ""



    @property
    def get_status(self):
        template = ""



        if self.rrso_status == -1:
            template += "<span class='badge badge-danger'>Rejected</span> | "

        elif self.rrso_status == 1:
            template += "<span class='badge badge-success'>Approved</span> | "

        else:
            template += "<span class='badge badge-primary'>Pending</span> | "

        if self.rso_status == -1:
            template += "<span class='badge badge-danger'>Rejected</span> | "

        elif self.rso_status == 1:
            template += "<span class='badge badge-success'>Approved</span> | "

        else:
            template += "<span class='badge badge-primary'>Pending</span> | "

        if self.attachment:
            template += "<span class='badge badge-success'>File</span>"

        else:
            template += "<span class='badge badge-default'>File</span>"

        return template

    class Meta:
        db_table = 'lds_rso'


class LdsRsoBudgetBaseline(models.Model):
    rso = models.ForeignKey('LdsRso', models.DO_NOTHING, db_column='rso_id')
    training = models.ForeignKey(Trainingtitle, models.DO_NOTHING, db_column='training_id')
    planned_participants = models.IntegerField(blank=True, null=True)
    planned_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    requested_participants = models.IntegerField(blank=True, null=True)
    requested_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'lds_rso_budget_baseline'


@receiver(models.signals.pre_save, sender=LdsRso)

def auto_delete_file_on_change(sender, instance, **kwargs):

    if not instance.pk:

        return False



    try:
        old_file = LdsRso.objects.get(pk=instance.pk).attachment
    except LdsRso.DoesNotExist:
        return False


    new_file = instance.attachment
    if old_file != new_file and old_file != '':
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)





class LdsIDP(models.Model):

    emp = models.ForeignKey(Empprofile, models.DO_NOTHING)
    year = models.CharField(max_length=255, blank=True, null=True)
    aim = models.CharField(max_length=1024, blank=True, null=True)
    date_created = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'lds_idp'


class LdsIDPType(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'lds_idp_type'


class LdsIDPContent(models.Model):
    type = models.ForeignKey('LdsIDPType', models.DO_NOTHING)
    title = models.CharField(max_length=1024, blank=True, null=True)
    cc_level = models.CharField(max_length=1024, blank=True, null=True)
    target_level = models.CharField(max_length=1024, blank=True, null=True)
    intervention = models.CharField(max_length=1024, blank=True, null=True)
    target_date = models.CharField(max_length=255, blank=True, null=True)
    results = models.CharField(max_length=1024, blank=True, null=True)
    remarks = models.CharField(max_length=1024, blank=True, null=True)
    idp = models.ForeignKey('LdsIDP', models.DO_NOTHING)



    class Meta:
        db_table = 'lds_idp_content'