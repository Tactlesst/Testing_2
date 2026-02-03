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


class LdsApprovedTrainingsDashboardSerializer(serializers.ModelSerializer):
    training_title = serializers.CharField(source='training.tt_name', read_only=True)
    date_added = serializers.DateTimeField(format="%b %d, %Y", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = LdsRso
        fields = ['id', 'training_title', 'date_added', 'status']

    def get_status(self, obj):
        try:
            if obj.rrso_status == 1 and obj.rso_status == 1:
                return 'Approved'
            if obj.rrso_status == -1 or obj.rso_status == -1:
                return 'Rejected'
            return 'Pending'
        except Exception:
            return 'Pending'
#nazef added

class LdsTrainingTitleListSerializer(serializers.ModelSerializer):
    added_by = serializers.SerializerMethodField()
    latest_venue = serializers.SerializerMethodField()
    latest_date_added = serializers.SerializerMethodField()
    latest_platform = serializers.SerializerMethodField()
    requests_count = serializers.IntegerField(read_only=True)
    trainees_count = serializers.IntegerField(read_only=True)
    facilitators_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Trainingtitle
        fields = [
            'id',
            'tt_name',
            'tt_status',
            'added_by',
            'latest_venue',
            'latest_date_added',
            'latest_platform',
            'requests_count',
            'trainees_count',
            'facilitators_count',
        ]

    def get_added_by(self, obj):
        try:
            if obj.pi_id and getattr(obj, 'pi', None) and getattr(obj.pi, 'user', None):
                return obj.pi.user.get_fullname
        except Exception:
            return ''
        return ''

    def get_latest_venue(self, obj):
        return getattr(obj, 'latest_venue', None) or ''

    def get_latest_date_added(self, obj):
        effective = getattr(obj, 'latest_date_added', None) or getattr(obj, 'latest_ldi_date_created', None)
        if not effective:
            return ''
        try:
            return effective.strftime('%Y-%m-%d')
        except Exception:
            return str(effective)

    def get_latest_platform(self, obj):
        platform = ''
        try:
            val = getattr(obj, 'latest_is_online_platform', None)
            if val is not None:
                platform = 'Online' if int(val) == 1 else 'Face-to-Face'
        except Exception:
            platform = ''

        if not platform:
            platform = getattr(obj, 'latest_ldi_platform', None) or ''
        return platform
#nazef end

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
