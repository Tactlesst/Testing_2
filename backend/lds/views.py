import math
from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from backend.documents.models import DtsDocument, DtsDrn, DtsTransaction, DtsDivisionCc
from backend.models import Designation, Empprofile, DRNTracker
from backend.views import generate_serial_string
from frontend.lds.models import LdsFacilitator, LdsParticipants, LdsRso
from frontend.models import PortalConfiguration
from frontend.templatetags.tags import generateDRN, gamify


@login_required
def ld_admin(request):
    context = {
        'tab_title': 'Learning and Development',
        'management': True,
        'title': 'ld_admin',
        'sub_title': 'train_request',
    }
    return render(request, 'backend/lds/rso.html', context)


#Nazef Added Functions
import os, json
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
    plans = read_plans()
    return render(request, 'backend/lds/ldi_list.html', {'plans': plans})

def ldi_plan(request, plan_id):
    categories = read_categories()
    message = None

    if request.method == "POST":
        category = request.POST.get('category')
        new_category = request.POST.get('new_category')
        activities = request.POST.get('activities').split('\n')
        title = activities[0] if activities else "New Plan"
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
            new_plan = {
                "id": f"LDI-{year}-000{len(plans)+1}",
                "title": title,
                "quarter": quarter,
                "year": year,
                "category": category,
                "activities": [a.strip() for a in activities if a.strip()],
                "participants": request.POST.get('participants'),
                "budget": request.POST.get('budget'),
                "competencies": request.POST.get('competencies'),
                "aim": request.POST.get('aim'),
                "status": "Pending Approval"
            }
            plans.append(new_plan)
            save_plans(plans)
            message = "LDI Plan saved successfully."

    return render(request, 'backend/lds/ldi_plan.html', {
        'categories': categories,
        'plan_id': plan_id,
        'message': message
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
    return JsonResponse({'data': 'success', 'msg': 'You have successfully approved the Request for Issuance of Regional Special Order'})


@login_required
@csrf_exempt
@permission_required('auth.ld_manager')
def bypass_lds_rso_approval(request, pk):
    LdsRso.objects.filter(id=pk).update(rso_status=1)
    return JsonResponse({'data': 'success', 'msg': 'You have successfully approved the Regional Special Order'})