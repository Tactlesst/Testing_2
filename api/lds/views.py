from datetime import datetime, time, timedelta
from django_mysql.models.functions import SHA1
from django.db.models import Count, OuterRef, Subquery, Q
from django.http import StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.lds.serializers import LdsRsoSerializer, LdsParticipantsSerializer, LdsFacilitatorSerializer, LdsIDPSerializer, LdsTrainingTitleListSerializer, LdsLdiPlanSerializer, LdsApprovedTrainingsDashboardSerializer, LdsTrainingNotificationsSerializer
from api.lds.sse import lds_notifications_broker
from backend.templatetags.tags import check_permission
from frontend.lds.models import LdsRso, LdsParticipants, LdsFacilitator, LdsIDP, LdsTrainingNotifications
from backend.lds.models import LdsLdiPlan
from backend.models import Empprofile
from frontend.models import Trainingtitle


class LdsLatestApprovedTrainingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        latest = (
            LdsRso.objects
            .filter(rrso_status=1, rso_status=1)
            .exclude(date_approved__isnull=True)
            .order_by('-date_approved', '-id')
            .select_related('training')
            .first()
        )

        if not latest:
            return Response({'has_latest': False})

        approved_at = latest.date_approved
        try:
            approved_at_iso = approved_at.isoformat() if approved_at else None
        except Exception:
            approved_at_iso = None

        return Response({
            'has_latest': True,
            'id': latest.id,
            'training_title': getattr(latest.training, 'tt_name', '') if latest.training_id else '',
            'date_approved': approved_at_iso,
        })


class LdsLatestApprovedTrainingNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        latest = (
            LdsTrainingNotifications.objects
            .select_related('training', 'training__training', 'approvedBy', 'approvedBy__pi__user')
            .order_by('-id')
            .first()
        )

        if not latest:
            return Response({'has_notification': False})

        return Response({
            'has_notification': True,
            'notification': LdsTrainingNotificationsSerializer(latest).data,
        })


class LdsTrainingNotificationsSseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        q = lds_notifications_broker.subscribe()

        def gen():
            try:
                yield ": stream-start\n\n"
                for chunk in lds_notifications_broker.event_stream(q):
                    yield chunk
            finally:
                lds_notifications_broker.unsubscribe(q)

        resp = StreamingHttpResponse(gen(), content_type='text/event-stream')
        resp['Cache-Control'] = 'no-cache'
        resp['X-Accel-Buffering'] = 'no'
        return resp


@login_required
def lds_training_notifications_sse(request):
    q = lds_notifications_broker.subscribe()

    def gen():
        try:
            yield ": stream-start\n\n"
            for chunk in lds_notifications_broker.event_stream(q):
                yield chunk
        finally:
            lds_notifications_broker.unsubscribe(q)

    resp = StreamingHttpResponse(gen(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp


class LdsRsoViews(generics.ListAPIView):
    serializer_class = LdsRsoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LdsRso.objects.annotate(hash=SHA1('created_by_id')).filter(hash=self.request.query_params.get('pk')).order_by('-date_added')
        return queryset


class LdsTrainingNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        emp = Empprofile.objects.filter(pi__user_id=request.user.id).first()
        if not emp:
            return Response({'state': 'none', 'has_training': False, 'message': ''})

        try:
            today = timezone.now().date()
        except Exception:
            today = datetime.now().date()

        participants_qs = (
            LdsParticipants.objects.select_related('rso', 'rso__training')
            .filter(
                emp_id=emp.id,
                rso__rrso_status=1,
                rso__rso_status=1,
            )
        )

        rso_qs = LdsRso.objects.filter(id__in=participants_qs.values('rso_id'))

        def _safe_date(dt):
            try:
                return dt.date() if dt else None
            except Exception:
                return None

        ongoing = []
        upcoming = []
        for rso in rso_qs.select_related('training'):
            start = _safe_date(rso.start_date)
            end = _safe_date(rso.end_date)
            if not start or not end:
                continue

            if start <= today <= end:
                ongoing.append((rso, start, end))
            elif today < start:
                upcoming.append((rso, start, end))

        chosen = None
        state = 'none'
        message = ''

        if ongoing:
            ongoing.sort(key=lambda x: (x[1], x[0].id))
            chosen = ongoing[0]
            state = 'ongoing'
            message = 'Training is Ongoing'
        elif upcoming:
            upcoming.sort(key=lambda x: (x[1], x[0].id))
            chosen = upcoming[0]
            rso, start, end = chosen
            days_to_start = (start - today).days
            if 1 <= days_to_start <= 2:
                state = 'near'
                message = 'Training Day is Near'
            else:
                state = 'upcoming'
                message = ''

        if not chosen:
            return Response({'state': 'none', 'has_training': False, 'message': ''})

        rso, start, end = chosen
        total_days = (end - start).days + 1
        elapsed_days = 0
        remaining_days = 0
        progress_percent = 0
        if total_days > 0:
            if today < start:
                elapsed_days = 0
                remaining_days = total_days
            elif today > end:
                elapsed_days = total_days
                remaining_days = 0
            else:
                elapsed_days = (today - start).days + 1
                remaining_days = (end - today).days

            try:
                progress_percent = int(round((elapsed_days / float(total_days)) * 100))
            except Exception:
                progress_percent = 0

        return Response({
            'state': state,
            'has_training': True,
            'message': message,
            'training': {
                'rso_id': rso.id,
                'title': getattr(rso.training, 'tt_name', '') if rso.training_id else '',
                'start_date': start.strftime('%b %d, %Y') if start else '',
                'end_date': end.strftime('%b %d, %Y') if end else '',
                'inclusive_dates': getattr(rso, 'get_inclusive_dates_v2', '') or getattr(rso, 'get_inclusive_dates', ''),
                'venue': rso.venue or '',
            },
            'progress': {
                'total_days': total_days,
                'elapsed_days': elapsed_days,
                'remaining_days': remaining_days,
                'percent': progress_percent,
            }
        })


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
        order_field = column_map.get(order_col, 'date_added')
        if order_field == 'date_approved':
            if order_dir == 'desc':
                qs = qs.order_by('-date_approved', '-date_added')
            else:
                qs = qs.order_by('date_approved', 'date_added')
        else:
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