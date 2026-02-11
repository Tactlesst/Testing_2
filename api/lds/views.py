from datetime import datetime, time, timedelta
from django_mysql.models.functions import SHA1
from django.db.models import Count, OuterRef, Subquery, Q
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.lds.serializers import LdsRsoSerializer, LdsParticipantsSerializer, LdsFacilitatorSerializer, LdsIDPSerializer, LdsTrainingTitleListSerializer, LdsLdiPlanSerializer, LdsApprovedTrainingsDashboardSerializer
from backend.templatetags.tags import check_permission
from frontend.lds.models import LdsRso, LdsParticipants, LdsFacilitator, LdsIDP
from backend.lds.models import LdsLdiPlan
from backend.models import Empprofile
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
        qs = (
            LdsRso.objects.select_related('training')
            .filter(rrso_status=1, rso_status=1)
            .order_by('-date_approved', '-date_added')
        )

        if (self.request.query_params.get('current_month') or '').strip() == '1':
            try:
                now_date = timezone.now().date()
            except Exception:
                now_date = datetime.now().date()

            month_start_date = now_date.replace(day=1)
            start_dt = datetime.combine(month_start_date, time.min)
            end_dt = datetime.combine(now_date + timedelta(days=1), time.min)

            if timezone.is_aware(timezone.now()):
                try:
                    start_dt = timezone.make_aware(start_dt)
                    end_dt = timezone.make_aware(end_dt)
                except Exception:
                    pass

            qs = qs.filter(
                Q(date_approved__gte=start_dt, date_approved__lt=end_dt)
                | Q(date_approved__isnull=True, date_added__gte=start_dt, date_added__lt=end_dt)
            )

        return qs

    def list(self, request, *args, **kwargs):
        draw = int(request.query_params.get('draw', '1') or 1)
        start = int(request.query_params.get('start', '0') or 0)
        length = int(request.query_params.get('length', '5') or 5)
        search_value = (request.query_params.get('search[value]') or '').strip()

        base_qs = self.get_queryset().distinct()
        records_total = base_qs.count()

        qs = base_qs
        if search_value:
            qs = qs.filter(Q(training__tt_name__icontains=search_value))

        records_filtered = qs.count()

        column_map = {
            0: 'training__tt_name',
            1: 'date_approved',
        }

        order_col = int(request.query_params.get('order[0][column]', '1') or 1)
        order_dir = request.query_params.get('order[0][dir]', 'desc')
        order_field = column_map.get(order_col, 'date_approved')
        if order_dir == 'desc':
            order_field = '-' + order_field
        qs = qs.order_by(order_field)

        page_qs = qs[start:start + length]

        serializer = self.get_serializer(page_qs, many=True)

        page_ids = [item.get('id') for item in serializer.data if item.get('id') is not None]
        date_added_map = {
            row_id: date_added
            for row_id, date_added in base_qs.filter(id__in=page_ids).values_list('id', 'date_added')
        }

        data = []
        for item in serializer.data:
            data_item = item.copy()
            if not data_item.get('date_approved'):
                date_added = date_added_map.get(data_item.get('id'))
                if date_added:
                    data_item['date_approved'] = date_added.strftime("%b %d, %Y")
            data.append(data_item)

        return Response({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
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


class LdsParticipantsByRsoDataTableViews(generics.ListAPIView):
    serializer_class = LdsParticipantsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        rso_id = self.kwargs.get('rso_id')
        return (
            LdsParticipants.objects.select_related('emp', 'emp__pi', 'emp__pi__user')
            .filter(rso_id=rso_id)
        )

    def list(self, request, *args, **kwargs):
        draw = int(request.query_params.get('draw', '1') or 1)
        start = int(request.query_params.get('start', '0') or 0)
        length = int(request.query_params.get('length', '10') or 10)
        search_value = (request.query_params.get('search[value]') or '').strip()

        base_qs = self.get_queryset()
        records_total = base_qs.count()

        qs = base_qs
        if search_value:
            qs = qs.filter(
                Q(participants_name__icontains=search_value)
                | Q(emp__pi__user__first_name__icontains=search_value)
                | Q(emp__pi__user__last_name__icontains=search_value)
            )

        records_filtered = qs.count()

        column_map = {
            0: 'emp__pi__user__last_name',
            1: 'type',
            2: 'emp__position__name',
        }

        order_col = int(request.query_params.get('order[0][column]', '0') or 0)
        order_dir = request.query_params.get('order[0][dir]', 'asc')
        order_field = column_map.get(order_col, 'emp__pi__user__last_name')
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