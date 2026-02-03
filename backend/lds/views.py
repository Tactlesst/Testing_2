import math
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.db.models import OuterRef, Subquery
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from backend.documents.models import DtsDocument, DtsDrn, DtsTransaction, DtsDivisionCc
from backend.models import Designation, Empprofile, DRNTracker
from backend.lds.models import LdsLdiPlan, LdsCategory
from backend.views import generate_serial_string
from frontend.lds.models import LdsFacilitator, LdsParticipants, LdsRso
from frontend.models import PortalConfiguration, Trainingtitle
from frontend.templatetags.tags import generateDRN, gamify


@login_required
def ld_admin(request):
    categories = LdsCategory.objects.filter(approve=1).order_by('category_name')
    context = {
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'train_request',
        'categories': categories,
    }
    return render(request, 'backend/lds/rso.html', context)


@login_required
def ldi_prototype(request):
    context = {
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'ldi_prototype',
    }
    return render(request, 'backend/lds/ldi_prototype.html', context)


@login_required
def ldi_approved_prototype(request):
    context = {
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'ldi_approved_prototype',
    }
    return render(request, 'backend/lds/ldi_approved_prototype.html', context)


# nazef working in this code start
@login_required
def lds_training_list(request):
    # nazef working in this code start
    training_titles = Trainingtitle.objects.select_related('pi__user').all().order_by('-id')
    # nazef working in this code end
    context = {
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'lds_training_list',
        # nazef working in this code start
        'training_titles': training_titles,
        # nazef working in this code end
    }
    return render(request, 'backend/lds/training_list.html', context)


@login_required
def lds_training_list_search(request):
    term = (request.GET.get('q') or '').strip()

    qs = Trainingtitle.objects.all()
    if term:
        qs = qs.filter(tt_name__icontains=term)

    qs = qs.order_by('tt_name')[:25]

    results = []
    for row in qs:
        results.append({
            'id': row.id,
            'text': row.tt_name,
        })

    return JsonResponse({'results': results})


@login_required
def lds_training_list_ajax(request):
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

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
    ).all()

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(ldsrso__date_added__date__gte=df)
        except ValueError:
            return JsonResponse({'error': True, 'msg': 'Invalid date_from.'}, status=400)

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(ldsrso__date_added__date__lte=dt)
        except ValueError:
            return JsonResponse({'error': True, 'msg': 'Invalid date_to.'}, status=400)

    qs = qs.distinct().order_by('-id')

    data = []
    for row in qs:
        platform = ''
        try:
            if row.latest_is_online_platform is not None:
                platform = 'Online' if int(row.latest_is_online_platform) == 1 else 'Face-to-Face'
        except Exception:
            platform = ''

        if not platform:
            platform = row.latest_ldi_platform or ''

        effective_date_added = row.latest_date_added or row.latest_ldi_date_created

        data.append({
            'id': row.id,
            'tt_name': row.tt_name,
            'tt_status': row.tt_status,
            'added_by': row.pi.user.get_fullname if row.pi_id and row.pi and row.pi.user_id else '',
            'requests_count': row.requests_count,
            'trainees_count': row.trainees_count,
            'facilitators_count': row.facilitators_count,
            'latest_venue': row.latest_venue or '',
            'latest_date_added': effective_date_added.strftime('%Y-%m-%d') if effective_date_added else '',
            'latest_platform': platform,
        })

    return JsonResponse({'data': data})


@login_required
def lds_training_list_details(request, training_id):
    training = Trainingtitle.objects.filter(id=training_id).first()
    qs = LdsRso.objects.select_related('created_by__pi__user').filter(training_id=training_id).annotate(
        participants_count=Count('ldsparticipants', distinct=True),
    ).order_by('-id')

    return render(request, 'backend/lds/training_title_details.html', {
        'training': training,
        'rows': qs,
    })


@login_required
def lds_training_list_participants(request, rso_id):
    rso = LdsRso.objects.select_related('training').filter(id=rso_id).first()

    facilitators = LdsFacilitator.objects.select_related('emp__pi__user').filter(
        rso_id=rso_id,
    ).order_by('order', 'id')

    internal_participants = LdsParticipants.objects.select_related('emp__pi__user').filter(
        rso_id=rso_id,
        type=0,
    ).order_by('order', 'id')

    external_participants = LdsParticipants.objects.filter(
        rso_id=rso_id,
        type=1,
    ).order_by('order', 'id')

    return render(request, 'backend/lds/training_rso_participants.html', {
        'rso': rso,
        'facilitators': facilitators,
        'internal_participants': internal_participants,
        'external_participants': external_participants,
    })


@login_required
def lds_training_list_details_ajax(request, training_id):
    qs = LdsRso.objects.select_related('created_by__pi__user').filter(training_id=training_id).annotate(
        participants_count=Count('ldsparticipants', distinct=True),
    ).order_by('-id')

    data = []
    for rso in qs:
        requester = ''
        if rso.created_by_id and getattr(rso.created_by, 'pi', None) and getattr(rso.created_by.pi, 'user', None):
            requester = rso.created_by.pi.user.get_fullname

        data.append({
            'id': rso.id,
            'requester': requester,
            'venue': rso.venue or '',
            'inclusive_dates': rso.get_inclusive_dates_v2,
            'participants_count': rso.participants_count,
        })

    return JsonResponse({'data': data})


@login_required
def lds_training_list_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': True, 'msg': 'Method not allowed'}, status=405)

    title = (request.POST.get('title') or '').strip()
    if not title:
        return JsonResponse({'error': True, 'msg': 'Title is required.'}, status=400)

    obj, created = Trainingtitle.objects.get_or_create(
        tt_name=title,
        defaults={
            'tt_status': 1,
            'pi_id': request.session.get('pi_id'),
        },
    )

    return JsonResponse({
        'data': 'success',
        'created': created,
        'id': obj.id,
        'text': obj.tt_name,
    })


@login_required
def lds_training_title_update(request, training_id):
    if request.method != 'POST':
        return JsonResponse({'error': True, 'msg': 'Method not allowed'}, status=405)

    title = (request.POST.get('title') or '').strip()
    if not title:
        return JsonResponse({'error': True, 'msg': 'Title is required.'}, status=400)

    updated = Trainingtitle.objects.filter(id=training_id).update(tt_name=title)
    if not updated:
        return JsonResponse({'error': True, 'msg': 'Training title not found.'}, status=404)

    return JsonResponse({'data': 'success', 'msg': 'Training title updated.'})


@login_required
def lds_training_title_delete(request, training_id):
    if request.method != 'POST':
        return JsonResponse({'error': True, 'msg': 'Method not allowed'}, status=405)

    if LdsRso.objects.filter(training_id=training_id).exists():
        return JsonResponse(
            {
                'error': True,
                'msg': 'Unable to delete. This training title has existing requests (participants/facilitators are linked to those requests).',
            },
            status=400,
        )

    obj = Trainingtitle.objects.filter(id=training_id).first()
    if not obj:
        return JsonResponse({'error': True, 'msg': 'Training title not found.'}, status=404)

    obj.delete()
    return JsonResponse({'data': 'success', 'msg': 'Training title deleted.'})
# nazef working in this code end


import os
from django.shortcuts import render, redirect
from django.conf import settings

MOCK_FILE = os.path.join(settings.BASE_DIR, 'backend/lds/mock_data.json')
CATEGORIES_FILE = os.path.join(settings.BASE_DIR, 'backend/lds/categories.json')
PENDING_FILE = os.path.join(settings.BASE_DIR, 'backend/lds/pending_categories.json')

def read_plans():
    if os.path.exists(MOCK_FILE):
        with open(MOCK_FILE, 'r') as f:
            return json.load(f)
    return []

def save_plans(plans):
    with open(MOCK_FILE, 'w') as f:
        json.dump(plans, f, indent=2)

def read_categories():
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, 'r') as f:
            return json.load(f)
    return ["Leadership Development", "Functional / Technical", "Values / Culture"]

def ldi_list(request):
    plans = list(LdsLdiPlan.objects.select_related('category', 'training').all().order_by('-id').values(
        'id',
        'category_id',
        'category__category_name',
        'training_id',
        'training__tt_name',
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
    ))

    for p in plans:
        p['training_category'] = p.get('category__category_name') or ''
        p['training_title'] = p.get('training__tt_name') or ''
    plans_json = json.dumps(plans, default=str)
    categories = list(LdsCategory.objects.filter(approve=1).order_by('category_name').values('id', 'category_name'))
    return render(request, 'backend/lds/ldi_list.html', {
        'plans': plans,
        'plans_json': plans_json,
        'categories': categories,
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'ldi_plan',
    })

@login_required
def ldi_list_ajax(request):
    draw = int(request.GET.get('draw', '1') or 1)
    start = int(request.GET.get('start', '0') or 0)
    length = int(request.GET.get('length', '25') or 25)
    search_value = (request.GET.get('search[value]') or '').strip()

    base_qs = LdsLdiPlan.objects.all()
    records_total = base_qs.count()

    qs = base_qs.select_related('category', 'training')
    if search_value:
        qs = qs.filter(
            Q(training__tt_name__icontains=search_value)
            | Q(category__category_name__icontains=search_value)
            | Q(platform__icontains=search_value)
            | Q(quarter__icontains=search_value)
            | Q(target_participants__icontains=search_value)
            | Q(venue__icontains=search_value)
        )

    records_filtered = qs.count()

    column_map = {
        1: 'id',
        2: 'training__tt_name',
        3: 'quarter',
        4: 'platform',
        5: 'category__category_name',
        6: 'budgetary_requirements',
        7: 'status',
    }

    order_col = int(request.GET.get('order[0][column]', '1') or 1)
    order_dir = request.GET.get('order[0][dir]', 'desc')
    order_field = column_map.get(order_col, 'id')
    if order_dir == 'desc':
        order_field = '-' + order_field
    qs = qs.order_by(order_field)

    qs = qs[start:start + length]

    data = []
    for row in qs:
        data.append({
            'id': row.id,
            'training_title': row.training.tt_name if row.training_id and row.training else '',
            'quarter': row.quarter or '',
            'platform': row.platform or '',
            'training_category': row.category.category_name if row.category_id and row.category else '',
            'budgetary_requirements': str(row.budgetary_requirements) if row.budgetary_requirements is not None else '',
            'status': row.status if row.status is not None else '',
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })

@login_required
def ldi_plan_get(request, pk):
    row = LdsLdiPlan.objects.select_related('category', 'training').filter(id=pk).values(
        'id',
        'category_id',
        'category__category_name',
        'training_id',
        'training__tt_name',
        'quarter',
        'platform',
        'proposed_ldi_activity',
        'proposed_date',
        'target_participants',
        'budgetary_requirements',
        'target_competencies',
        'venue',
        'status',
    ).first()

    if not row:
        return JsonResponse({'error': True, 'msg': 'Plan not found.'}, status=404)

    row['budgetary_requirements'] = str(row['budgetary_requirements']) if row.get('budgetary_requirements') is not None else ''
    row['proposed_date'] = str(row['proposed_date']) if row.get('proposed_date') else ''
    row['training_category'] = row.get('category__category_name') or ''
    row['training_title'] = row.get('training__tt_name') or ''
    row['proposed_ldi_activity'] = row.get('proposed_ldi_activity') or ''

    return JsonResponse({'data': 'success', 'row': row})

@login_required
def ldi_plan_get_by_training(request, training_id):
    row = (
        LdsLdiPlan.objects.select_related('category', 'training')
        .filter(training_id=training_id)
        .order_by('-id')
        .values(
            'id',
            'category_id',
            'category__category_name',
            'training_id',
            'training__tt_name',
            'quarter',
            'platform',
            'proposed_ldi_activity',
            'proposed_date',
            'target_participants',
            'budgetary_requirements',
            'target_competencies',
            'venue',
            'status',
        )
        .first()
    )

    if not row:
        return JsonResponse({'error': True, 'msg': 'No plan found for this training title.'}, status=404)

    row['budgetary_requirements'] = str(row['budgetary_requirements']) if row.get('budgetary_requirements') is not None else ''
    row['proposed_date'] = str(row['proposed_date']) if row.get('proposed_date') else ''
    row['training_category'] = row.get('category__category_name') or ''
    row['training_title'] = row.get('training__tt_name') or ''
    row['proposed_ldi_activity'] = row.get('proposed_ldi_activity') or ''

    return JsonResponse({'data': 'success', 'row': row})

@login_required
def ldi_plan_details(request, training_id):
    training = Trainingtitle.objects.filter(id=training_id).first()
    rows = LdsLdiPlan.objects.select_related('category', 'training').filter(training_id=training_id).order_by('-id')

    request_rows = LdsRso.objects.select_related('created_by__pi__user').filter(training_id=training_id).annotate(
        participants_count=Count('ldsparticipants', distinct=True),
    ).order_by('-id')

    rso = (
        LdsRso.objects.select_related('training')
        .filter(training_id=training_id)
        .order_by('-date_added', '-id')
        .first()
    )

    facilitators = []
    internal_participants = []
    external_participants = []
    if rso:
        facilitators = LdsFacilitator.objects.select_related('emp__pi__user').filter(
            rso_id=rso.id,
        ).order_by('order', 'id')

        internal_participants = LdsParticipants.objects.select_related('emp__pi__user').filter(
            rso_id=rso.id,
            type=0,
        ).order_by('order', 'id')

        external_participants = LdsParticipants.objects.filter(
            rso_id=rso.id,
            type=1,
        ).order_by('order', 'id')

    activities_text = ''
    first = rows.first()
    if first and getattr(first, 'proposed_ldi_activity', None):
        activities_text = first.proposed_ldi_activity

    context = {
        'training': training,
        'rows': rows,
        'request_rows': request_rows,
        'activities_text': activities_text,
        'training_id': training_id,  # Pass training_id as backup
        'rso': rso,
        'facilitators': facilitators,
        'internal_participants': internal_participants,
        'external_participants': external_participants,
    }
    return render(request, 'backend/lds/ldi_plan_details.html', context)

@login_required
def ldi_plan_save(request):
    if request.method != 'POST':
        return JsonResponse({'error': True, 'msg': 'Method not allowed'}, status=405)

    pk = (request.POST.get('ldi_id') or '').strip()
    training_id = (request.POST.get('training_id') or '').strip()
    category_id = (request.POST.get('category_id') or '').strip()
    training_title = (request.POST.get('training_title') or '').strip()
    training_category = (request.POST.get('training_category') or '').strip()

    quarter = (request.POST.get('quarter') or '').strip()
    platform = (request.POST.get('platform') or '').strip()
    proposed_ldi_activity = (request.POST.get('proposed_ldi_activity') or '').strip()
    proposed_date = (request.POST.get('proposed_date') or '').strip()
    target_participants = (request.POST.get('target_participants') or '').strip()

    proposed_date_value = None
    if proposed_date:
        try:
            proposed_date_value = datetime.strptime(proposed_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': True, 'msg': 'Invalid proposed date.'}, status=400)

    if not training_id and not training_title:
        return JsonResponse({'error': True, 'msg': 'Training title is required.'}, status=400)
    if not quarter:
        return JsonResponse({'error': True, 'msg': 'Quarter is required.'}, status=400)
    if not platform:
        return JsonResponse({'error': True, 'msg': 'Platform is required.'}, status=400)
    if not proposed_ldi_activity:
        return JsonResponse({'error': True, 'msg': 'Proposed LDI / activities is required.'}, status=400)

    category_obj = None
    if category_id:
        category_obj = LdsCategory.objects.filter(id=category_id).first()
        if not category_obj:
            return JsonResponse({'error': True, 'msg': 'Selected training category not found.'}, status=400)
    elif training_category:
        category_obj, _ = LdsCategory.objects.get_or_create(
            category_name=training_category,
            defaults={'approve': 1},
        )

    training_obj = None
    if training_id:
        training_obj = Trainingtitle.objects.filter(id=training_id).first()
        if not training_obj:
            return JsonResponse({'error': True, 'msg': 'Selected training title not found.'}, status=400)
    else:
        training_obj = Trainingtitle.objects.filter(tt_name=training_title).first()
        if not training_obj:
            training_obj = Trainingtitle.objects.create(
                tt_name=training_title,
                tt_status=1,
                pi_id=request.session.get('pi_id'),
            )

    defaults = {
        'category_id': category_obj.id if category_obj else None,
        'quarter': quarter,
        'platform': platform,
        'training_id': training_obj.id,
        'proposed_ldi_activity': proposed_ldi_activity,
        'proposed_date': proposed_date_value,
        'target_participants': target_participants,
        'budgetary_requirements': request.POST.get('budgetary_requirements'),
        'target_competencies': request.POST.get('target_competencies'),
        'venue': request.POST.get('venue'),
        'status': 1,
    }

    if pk:
        defaults['date_updated'] = timezone.now()
        LdsLdiPlan.objects.filter(id=pk).update(**defaults)
        return JsonResponse({'data': 'success', 'msg': 'LDI plan updated.'})

    defaults['date_created'] = timezone.now()
    emp_id = request.session.get('emp_id')
    if emp_id and Empprofile.objects.filter(id=emp_id).exists():
        defaults['created_by_id'] = emp_id
    else:
        defaults['created_by_id'] = None
    defaults['date_approved'] = timezone.now()
    obj = LdsLdiPlan.objects.create(**defaults)
    return JsonResponse({'data': 'success', 'msg': 'LDI plan created.', 'id': obj.id})

@login_required
def ldi_plan_delete(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': True, 'msg': 'Method not allowed'}, status=405)

    obj = LdsLdiPlan.objects.filter(id=pk).first()
    if not obj:
        return JsonResponse({'error': True, 'msg': 'Plan not found.'}, status=404)

    try:
        with transaction.atomic():
            for rel in obj._meta.related_objects:
                accessor = rel.get_accessor_name()
                if not accessor:
                    continue

                try:
                    related_manager = getattr(obj, accessor, None)
                except Exception:
                    related_manager = None

                if related_manager is None:
                    continue

                try:
                    related_manager.all().delete()
                except Exception:
                    pass

            obj.delete()
    except IntegrityError:
        return JsonResponse(
            {
                'error': True,
                'msg': 'Unable to delete. This LDI plan is still referenced by other records.',
            },
            status=400,
        )

def ldi_plan(request, plan_id):
    categories = read_categories()
    message = None

    plans = read_plans()
    plan = None
    for p in plans:
        if str(p.get('id')) == str(plan_id):
            plan = p
            break

    if plan is None:
        plan = {
            'id': '',
            'training_title': '',
            'quarter': 'Q1',
            'year': timezone.now().year,
            'category': categories[0] if categories else '',
            'activities': [],
            'participants': '',
            'budget': '',
            'competencies': '',
            'aim': '',
            'proposed_date': str(timezone.now().date()),
            'status': 'Pending Approval',
        }

    if request.method == "POST":
        category = request.POST.get('category')
        new_category = request.POST.get('new_category')
        training_title = (request.POST.get('training_title') or '').strip()
        activities = (request.POST.get('activities') or '').split('\n')
        quarter = request.POST.get('quarter')
        year = request.POST.get('year')

        # Handle new category
        if category == "_new" and new_category:
            pending = []
            if os.path.exists(PENDING_FILE):
                with open(PENDING_FILE, 'r') as f:
                    pending = json.load(f)
            if new_category not in pending:
                pending.append(new_category)
                with open(PENDING_FILE, 'w') as f:
                    json.dump(pending, f, indent=2)
            message = f"New category '{new_category}' submitted for approval."
        else:
            # Save plan to mock_data
            plans = read_plans()
            existing_index = None
            for i, p in enumerate(plans):
                if str(p.get('id')) == str(plan_id):
                    existing_index = i
                    break

            next_number = len(plans) + 1
            try:
                next_number = max([int(str(x.get('id', '')).split('-')[-1]) for x in plans if str(x.get('id', '')).startswith(f"LDI-{year}-")]) + 1
            except Exception:
                pass

            new_id = str(plan_id)
            if not new_id or new_id.lower() == 'new':
                new_id = f"LDI-{year}-{str(next_number).zfill(4)}"

            new_plan = {
                "id": new_id,
                "training_title": training_title,
                "quarter": quarter,
                "year": year,
                "category": category,
                "activities": [a.strip() for a in activities if a.strip()],
                "participants": request.POST.get('participants'),
                "budget": request.POST.get('budget'),
                "competencies": request.POST.get('competencies'),
                "aim": request.POST.get('aim'),
                "proposed_date": request.POST.get('proposed_date'),
                "status": "Pending Approval"
            }

            if existing_index is not None:
                plans[existing_index] = new_plan
            else:
                plans.append(new_plan)
            save_plans(plans)
            message = "LDI Plan saved successfully."

            plan = new_plan

    return render(request, 'backend/lds/ldi_plan.html', {
        'categories': categories,
        'plan_id': plan_id,
        'plan': plan,
        'message': message,
        'today': str(timezone.now().date()),
        'current_year': timezone.now().year,
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'ldi_plan',
    })

#End Nazef Added Functions

@login_required
@permission_required('auth.training_requester')

def print_rso(request, pk):
    if request.method == "POST":
        check = DRNTracker.objects.filter(value=pk)
        if not check:
            DRNTracker.objects.create(
                drn=request.POST.get('drn'),
                value=pk,
                emp_id=request.session['emp_id']
            )
        else:
            check.update(
                drn=request.POST.get('drn')
            )

        return JsonResponse({'data': 'success', 'msg': 'You have successfully updated the DRN.'})

    data = []
    facilitators = LdsFacilitator.objects.filter(rso_id=pk, is_external=0).order_by('-order', 'emp__pi__user__last_name')
    ex_facilitators = LdsFacilitator.objects.filter(rso_id=pk, is_external=1).order_by('-order', 'rp_name')
    internal_participants = LdsParticipants.objects.filter(rso_id=pk, type=0).order_by('-order', 'emp__pi__user__last_name')
    external_participants = LdsParticipants.objects.filter(rso_id=pk, type=1).order_by('-order', 'participants_name')

    # f_counter = 1
    # for row in facilitators:
    #     if f_counter == 1:
    #         data.append({
    #             'full_name': 'FACILITATOR / RESOURCE PERSON',
    #             'position': 1
    #         })

    #         data.append({
    #             'id': f_counter,
    #             'full_name': row.emp.pi.user.get_fullname,
    #             'position': row.emp.position.name
    #         })
    #     else:
    #         data.append({
    #             'id': f_counter - 1,
    #             'full_name': row.emp.pi.user.get_fullname,
    #             'position': row.emp.position.name
    #         })

    #     f_counter = f_counter + 1

    f_counter = 1
    data.append({
        'full_name': 'FACILITATOR / RESOURCE PERSON',
        'position': 1 
    })

    for row in facilitators:
        data.append({
            'id': f_counter,  
            'full_name': row.emp.pi.user.get_fullname,
            'position': row.emp.position.name
        })
        f_counter += 1 


    ef_counter = 1
    for row in ex_facilitators:
        if ef_counter == 1:
            data.append({
                'full_name': 'EXTERNAL FACILITATOR / RESOURCE PERSON',
                'position': 0
            })

            data.append({
                'id': ef_counter,
                'full_name': row.rp_name,
                'position': None
            })
        else:
            data.append({
                'id': ef_counter - 1,
                'full_name': row.rp_name,
                'position': None
            })

        ef_counter = ef_counter + 1

    ip_counter = 1
    for row in internal_participants:
        if ip_counter == 1:
            data.append({
                'full_name': 'INTERNAL PARTICIPANTS',
                'position': 1
            })

            data.append({
                'id': ip_counter,
                'full_name': row.emp.pi.user.get_fullname,
                'position': row.emp.position.name
            })
        else:
            data.append({
                'id': ip_counter,
                'full_name': row.emp.pi.user.get_fullname,
                'position': row.emp.position.name
            })

        ip_counter = ip_counter + 1

    ep_counter = 1
    for row in external_participants:
        if ep_counter == 1:
            data.append({
                'full_name': 'EXTERNAL PARTICIPANTS',
                'position': 0
            })

            data.append({
                'id': ep_counter,
                'full_name': row.participants_name,
                'position': None
            })
        else:
            data.append({
                'id': ep_counter - 1,
                'full_name': row.participants_name,
                'position': None
            })

        ep_counter = ep_counter + 1

    first_page = data[:23]
    pages = data[23:]
    total_pages = len(first_page) + len(pages)

    context = {
        'first_page': first_page,
        'pagination': math.ceil(float(len(pages)) / 40) + 1 if total_pages > 23 else math.ceil(float(len(first_page)) / 23),
        'actual_pagination': math.ceil(float(len(pages)) / 40),
        'pages': pages,
        'today': datetime.now(),
        'training': LdsRso.objects.filter(id=pk).first(),
        'rd': Designation.objects.filter(id=1).first(),
    }
    return render(request, 'backend/lds/print_rso.html', context)


@login_required
def generate_drn_for_rso(request):
    if request.method == "POST":
        lasttrack = DtsDocument.objects.order_by('-id').first()
        track_num = generate_serial_string(lasttrack.tracking_no) if lasttrack else \
            generate_serial_string(None, 'DT')

        sender = Empprofile.objects.filter(id=request.session['emp_id']).first()
        document = DtsDocument(
            doctype_id=20,
            docorigin_id=2,
            sender=sender.pi.user.get_fullname,
            subject="Regional Special Order",
            other_info=request.POST.get('other_info'),
            purpose="For Signature",
            document_date=datetime.now(),
            document_deadline=None,
            tracking_no=track_num,
            creator_id=request.session['emp_id'],
            drn=None
        )

        document.save()

        drn_data = DtsDrn(
            document_id=document.id,
            category_id=1,
            doctype_id=20,
            division_id=1,
            section_id=None
        )

        drn_data.save()

        generated_drn = generateDRN(document.id, drn_data.id, True)
        config = PortalConfiguration.objects.filter(key_name='RSO').first()

        if document:
            for x in range(2):
                DtsTransaction.objects.create(
                    action=x,
                    trans_from_id=request.session['emp_id'],
                    trans_to_id=config.key_acronym,
                    trans_datestarted=None,
                    trans_datecompleted=None,
                    action_taken=None,
                    document_id=document.id
                )

        DtsDivisionCc.objects.create(
            document_id=document.id,
            division_id=1
        )

        DRNTracker.objects.create(
            drn=generated_drn,
            value=request.POST.get('training_id'),
            emp_id=request.POST.get('emp_id')
        )

        LdsRso.objects.filter(id=request.POST.get('training_id')).update(
            rrso_status=1
        )
        return JsonResponse({'data': 'success', 'drn': generated_drn})


@login_required
@csrf_exempt
@permission_required('auth.ld_manager')
def bypass_lds_rrso_approval(request, pk):
    LdsRso.objects.filter(id=pk).update(rrso_status=1)

    rso = LdsRso.objects.filter(id=pk).only('id', 'rrso_status', 'rso_status', 'date_approved').first()
    if rso and rso.rrso_status == 1 and rso.rso_status == 1 and not rso.date_approved:
        LdsRso.objects.filter(id=pk).update(date_approved=timezone.now())
    return JsonResponse({'data': 'success', 'msg': 'You have successfully approved the Request for Issuance of Regional Special Order'})


@login_required
@csrf_exempt
@permission_required('auth.ld_manager')
def bypass_lds_rso_approval(request, pk):
    LdsRso.objects.filter(id=pk).update(rso_status=1)

    rso = LdsRso.objects.filter(id=pk).only('id', 'rrso_status', 'rso_status', 'date_approved').first()
    if rso and rso.rrso_status == 1 and rso.rso_status == 1 and not rso.date_approved:
        LdsRso.objects.filter(id=pk).update(date_approved=timezone.now())
    return JsonResponse({'data': 'success', 'msg': 'You have successfully approved the Regional Special Order'})


@login_required
@permission_required('auth.ld_manager')
def training_details_admin(request, pk):
    """Admin view for training details with action buttons"""
    obj = get_object_or_404(LdsRso, pk=pk)
    context = {
        'training': obj,
        'participants': LdsParticipants.objects.filter(rso_id=pk).order_by('emp__pi__user__last_name'),
        'facilitators': LdsFacilitator.objects.filter(rso_id=pk).order_by('emp__pi__user__last_name'),
        'is_admin': True,
    }
    return render(request, 'backend/lds/training_details_admin.html', context)


@login_required
@csrf_exempt
@permission_required('auth.ld_manager')
def reject_training(request, pk):
    """Handle training rejection - sets status to -1"""
    if request.method == "POST":
        try:
            training = get_object_or_404(LdsRso, pk=pk)
            
            # Mark as rejected by setting status to -1
            training.rrso_status = -1
            training.rso_status = -1
            training.save()
            
            return JsonResponse({'data': 'success', 'msg': 'Training has been rejected successfully.'})
        except Exception as e:
            return JsonResponse({'error': True, 'msg': str(e)}, status=500)
    
    return JsonResponse({'error': True, 'msg': 'Invalid request method.'}, status=400)