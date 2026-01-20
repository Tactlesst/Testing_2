from rest_framework import serializers

from frontend.lds.models import LdsRso, LdsParticipants, LdsFacilitator, LdsIDP
from backend.lds.models import LdsLdiPlan, LdsCategory
from frontend.models import Trainingtitle


class LdsRsoSerializer(serializers.ModelSerializer):
    training_title = serializers.CharField(source='training.tt_name', read_only=True)
    inclusive_dates = serializers.CharField(source='get_inclusive_dates', read_only=True)
    time_range = serializers.CharField(source='get_time_range', read_only=True)
    date_added = serializers.DateTimeField(format="%b %d, %Y %H:%M:%S %p", read_only=True)
    status = serializers.CharField(source='get_status', read_only=True)
    created_by = serializers.CharField(source='created_by.pi.user.get_fullname', read_only=True)

    class Meta:
        model = LdsRso
        fields = ['id', 'training_title', 'inclusive_dates', 'date_added', 'status', 'venue', 'created_by', 'time_range']


class LdsParticipantsSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='emp.pi.user.get_fullname', read_only=True)
    position = serializers.CharField(source='emp.position.name', read_only=True)
    type = serializers.CharField(source='get_participant_type', read_only=True)

    class Meta:
        model = LdsParticipants
        fields = ['id', 'rso_id', 'full_name', 'type', 'position', 'participants_name']


class LdsFacilitatorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='emp.pi.user.get_fullname', read_only=True)
    position = serializers.CharField(source='emp.position.name', read_only=True)

    class Meta:
        model = LdsFacilitator
        fields = ['id', 'rso_id', 'full_name', 'is_resource_person', 'position', 'emp_id', 'rp_name', 'is_group']


class LdsIDPSerializer(serializers.ModelSerializer):
    date_created = serializers.DateTimeField(format="%b %d, %Y %H:%M:%S %p", read_only=True)
    date_updated = serializers.DateTimeField(format="%b %d, %Y %H:%M:%S %p", read_only=True)

    class Meta:
        model = LdsIDP
        fields = '__all__'


class LdsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LdsCategory
        fields = ['id', 'category_name', 'approve']


class TrainingtitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trainingtitle
        fields = ['id', 'tt_name', 'tt_status']


class LdsLdiPlanSerializer(serializers.ModelSerializer):
    training_title = serializers.CharField(source='training.tt_name', read_only=True)
    training_id = serializers.IntegerField(required=False, allow_null=True)
    training = TrainingtitleSerializer(read_only=True)

    training_category = serializers.CharField(source='category.category_name', read_only=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    category = LdsCategorySerializer(read_only=True)

    class Meta:
        model = LdsLdiPlan
        fields = [
            'id',
            'training_id',
            'training_title',
            'training',
            'category_id',
            'training_category',
            'category',
            'quarter',
            'platform',
            'proposed_ldi_activity',
            'proposed_date',
            'target_participants',
            'budgetary_requirements',
            'target_competencies',
            'venue',
            'status',
            'date_created',
            'date_updated',
            'date_approved',
        ]
