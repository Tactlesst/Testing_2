from django_mysql.models.functions import SHA1
from django.db.models import Count, OuterRef, Subquery, Q
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.lds.serializers import LdsRsoSerializer, LdsParticipantsSerializer, LdsFacilitatorSerializer, LdsIDPSerializer, LdsTrainingTitleListSerializer, LdsLdiPlanSerializer, LdsApprovedTrainingsDashboardSerializer
from backend.templatetags.tags import check_permission
from frontend.lds.models import LdsRso, LdsParticipants, LdsFacilitator, LdsIDP
from backend.lds.models import LdsLdiPlan
from frontend.models import Trainingtitle


class LdsRsoViews(generics.ListAPIView):
    serializer_class = LdsRsoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LdsRso.objects.annotate(hash=SHA1('created_by_id')).filter(hash=self.request.query_params.get('pk')).order_by('-date_added')
        return queryset


class LdsManagerPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if check_permission(request.user, 'ld_manager') or check_permission(request.user, 'superadmin'):
            return True
        else:
            return False


class LdsRsoViewsAdmin(generics.ListAPIView):
    serializer_class = LdsRsoSerializer
    permission_classes = [IsAuthenticated, LdsManagerPermissions]
    queryset = LdsRso.objects.order_by('-date_added')


class LdsApprovedTrainingsDashboardDataTableViews(generics.ListAPIView):
    serializer_class = LdsApprovedTrainingsDashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            LdsRso.objects.select_related('training')
            .order_by('-date_approved', '-date_added')
        )

    def _apply_status_filter(self, qs, status):
        status = (status or '').strip().lower()
        if not status:
            return qs

        if status == 'approved':
            return qs.filter(rrso_status=1, rso_status=1)
        if status == 'rejected':
            return qs.filter(Q(rrso_status=-1) | Q(rso_status=-1))
        if status == 'pending':
            return qs.exclude(Q(rrso_status=-1) | Q(rso_status=-1)).exclude(Q(rrso_status=1) & Q(rso_status=1))

        return qs

    def list(self, request, *args, **kwargs):
        draw = int(request.query_params.get('draw', '1') or 1)
        start = int(request.query_params.get('start', '0') or 0)
        length = int(request.query_params.get('length', '5') or 5)
        search_value = (request.query_params.get('search[value]') or '').strip()
        status_filter = request.query_params.get('status')

        base_qs = self._apply_status_filter(self.get_queryset().distinct(), status_filter)
        records_total = base_qs.count()

        qs = base_qs
        if search_value:
            qs = qs.filter(Q(training__tt_name__icontains=search_value))

        records_filtered = qs.count()

        column_map = {
            0: 'training__tt_name',
            1: 'date_added',
        }

        order_col = int(request.query_params.get('order[0][column]', '1') or 1)
        order_dir = request.query_params.get('order[0][dir]', 'desc')
        order_field = column_map.get(order_col, 'date_added')
        if order_dir == 'desc':
            order_field = '-' + order_field
        qs = qs.order_by(order_field)

        qs = qs[start:start + length]

        serializer = self.get_serializer(qs, many=True)
        return Response({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': serializer.data,
        })


class LdsParticipantsViews(generics.ListAPIView):
    serializer_class = LdsParticipantsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LdsParticipants.objects.annotate(type_pk=SHA1('type'), rso_pk=SHA1('rso_id')).filter(
            type_pk=self.request.query_params.get('type_pk'),
            rso_pk=self.request.query_params.get('rso_pk')
        ).order_by('emp__pi__user__last_name')
        return queryset


class LdsFacilitatorsViews(generics.ListAPIView):
    serializer_class = LdsFacilitatorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LdsFacilitator.objects.annotate(rso_pk=SHA1('rso_id'), type_pk=SHA1('is_external')).filter(
            type_pk=self.request.query_params.get('type_pk'),
            rso_pk=self.request.query_params.get('rso_pk')
        ).order_by('emp__pi__user__last_name')
        return queryset


class LdsIDPViews(generics.ListAPIView):
    serializer_class = LdsIDPSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LdsIDP.objects.annotate(emp_pk=SHA1('emp_id')).filter(
            emp_pk=self.request.query_params.get('emp_pk')
        ).order_by('-date_created')
        return queryset


#nazef Added
class LdsTrainingTitlesDataTableViews(generics.ListAPIView):
    serializer_class = LdsTrainingTitleListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        latest_rso = LdsRso.objects.filter(training_id=OuterRef('pk')).order_by('-date_added', '-id')
        latest_ldi = LdsLdiPlan.objects.filter(training_id=OuterRef('pk')).order_by('-date_created', '-id')

        qs = Trainingtitle.objects.select_related('pi__user').annotate(
            requests_count=Count('ldsrso', distinct=True),
            trainees_count=Count('ldsrso__ldsparticipants', distinct=True),
            facilitators_count=Count('ldsrso__ldsfacilitator', distinct=True),
            latest_venue=Subquery(latest_ldi.values('venue')[:1]),
            latest_date_added=Subquery(latest_rso.values('date_added')[:1]),
            latest_is_online_platform=Subquery(latest_rso.values('is_online_platform')[:1]),
            latest_ldi_date_created=Subquery(latest_ldi.values('date_created')[:1]),
            latest_ldi_platform=Subquery(latest_ldi.values('platform')[:1]),
        )

        return qs

    def list(self, request, *args, **kwargs):
        draw = int(request.query_params.get('draw', '1') or 1)
        start = int(request.query_params.get('start', '0') or 0)
        length = int(request.query_params.get('length', '25') or 25)
        search_value = (request.query_params.get('search[value]') or '').strip()

        base_qs = self.get_queryset().distinct()
        records_total = base_qs.count()

        qs = base_qs
        if search_value:
            qs = qs.filter(
                Q(tt_name__icontains=search_value)
                | Q(pi__user__first_name__icontains=search_value)
                | Q(pi__user__last_name__icontains=search_value)
                | Q(latest_venue__icontains=search_value)
            )

        records_filtered = qs.count()

        column_map = {
            1: 'id',
            2: 'tt_name',
            3: 'tt_status',
            4: 'pi__user__last_name',
            5: 'latest_venue',
            6: 'latest_date_added',
            7: 'latest_is_online_platform',
            8: 'requests_count',
            9: 'trainees_count',
            10: 'facilitators_count',
        }

        order_col = int(request.query_params.get('order[0][column]', '1') or 1)
        order_dir = request.query_params.get('order[0][dir]', 'desc')
        order_field = column_map.get(order_col, 'id')
        if order_dir == 'desc':
            order_field = '-' + order_field
        qs = qs.order_by(order_field)

        qs = qs[start:start + length]

        serializer = self.get_serializer(qs, many=True)
        return Response({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': serializer.data,
        })


class LdsLdiPlansByTrainingViews(generics.ListAPIView):
    serializer_class = LdsLdiPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        training_id = self.kwargs.get('training_id')
        return (
            LdsLdiPlan.objects.select_related('category', 'training')
            .filter(training_id=training_id)
            .order_by('-id')
        )


#nazef end