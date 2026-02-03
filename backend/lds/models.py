from django.db import models

from backend.models import Empprofile
from frontend.models import Trainingtitle


class LdsCategory(models.Model):
    category_name = models.CharField(max_length=255)
    approve = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lds_category'


class LdsLdiPlan(models.Model):
    category = models.ForeignKey(LdsCategory, models.DO_NOTHING, db_column='category_id', blank=True, null=True)
    quarter = models.CharField(max_length=10, blank=True, null=True)
    platform = models.CharField(max_length=255, blank=True, null=True)
    training = models.ForeignKey(Trainingtitle, models.CASCADE, db_column='training_id', blank=True, null=True)
    proposed_ldi_activity = models.TextField(blank=True, null=True)
    proposed_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    target_participants = models.TextField(blank=True, null=True)
    budgetary_requirements = models.TextField(blank=True, null=True)
    target_competencies = models.TextField(blank=True, null=True)
    venue = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(Empprofile, models.DO_NOTHING, db_column='created_by_id', blank=True, null=True)
    manager_id = models.IntegerField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    rejection_remarks = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    date_updated = models.DateTimeField(blank=True, null=True)
    date_approved = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lds_ldi_plan'
