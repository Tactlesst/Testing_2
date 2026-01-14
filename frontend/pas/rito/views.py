# --- Standard Library ---
import re
import json
import io
import os
import math
from datetime import datetime, date
import base64
import requests

# --- Django ---
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt

# --- Third-party / external libraries ---
from django_mysql.models.functions import SHA1

# --- Backend models ---
from backend.models import Empprofile, Section, Division, Designation
from backend.libraries.leave.models import LeaveSubtype, LeavespentApplication

# --- Frontend models ---
from frontend.models import (
    Rito, Ritodetails, Ritopeople, Claims, Mot,
    PortalConfiguration, RitoAttachment, RitoSignatories, Subject
)
from backend.libraries.leave.models import LeaveSignatories, Signature

# --- Frontend utils / functions ---
from frontend.pas.rito.functions import check_signatories_rito_workflow
from frontend.templatetags.tags import gamify
from frontend.leave.crypto import decrypt_text
from frontend.leave.views import validate_p12_certificate

from django.views.decorators.http import require_http_methods
from frontend.pas.rito.utils import multiple_travel_signatories,generate_validated_signature_stamp
 




def check_rito_confirmation_function(inclusive_from, emp_id):
    ritodetail = Ritodetails.objects.filter(Q(rito__status=1) & Q(rito__emp_id=emp_id)).first()
    for_confirm_rito = False
    not_for_confirm_rito = False
    
    if isinstance(inclusive_from, str):
        inclusive_from = datetime.strptime(inclusive_from, '%Y-%m-%d')
    elif isinstance(inclusive_from, datetime):
        pass
    else:
        inclusive_from = datetime.combine(inclusive_from, datetime.min.time())

    if ritodetail:
        ritodetail_date = ritodetail.inclusive_from.date() if isinstance(ritodetail.inclusive_from, datetime) else ritodetail.inclusive_from
        
        if date.today() > ritodetail_date:
            for_confirm_rito = True
        else:
            not_for_confirm_rito = True

    inclusive_from_date = inclusive_from.date() if isinstance(inclusive_from, datetime) else inclusive_from
    
    if date.today() > inclusive_from_date:
        for_confirm_rito = True
    else:
        not_for_confirm_rito = True

    return True if for_confirm_rito and not_for_confirm_rito else False


# @login_required
# @permission_required('auth.travel_order')
# def get_travel_totals(request):
#     total_requests = Rito.objects.filter(emp_id=request.session['emp_id'], status__in=[2, 3, 5]).count()
#     total_drafts = Rito.objects.filter(emp_id=request.session['emp_id'], status=4).count()
#     init_requests = Rito.objects.filter(emp_id=request.session['emp_id'], status=1).first()
#     for_approval = RitoSignatories.objects.filter(status=0, emp_id=request.session['emp_id']).count()

#     if init_requests:
#         total_init_requests = Ritodetails.objects.filter(rito_id=init_requests.id).count()
#     else:
#         total_init_requests = 0
#     return JsonResponse({'drafts': total_drafts,
#                          'requests': total_requests,
#                          'init_requests': total_init_requests,
#                          'for_approval': for_approval})


@login_required
@permission_required('auth.travel_order')
def get_travel_totals(request):
    
    current_emp_id = request.session['emp_id']
    
    total_requests = Rito.objects.filter(emp_id=current_emp_id, status__in=[2, 3, 5]).count()
    total_drafts = Rito.objects.filter(emp_id=current_emp_id, status=4).count()
    init_requests = Rito.objects.filter(emp_id=current_emp_id, status=1).first()

    
    if init_requests:
        total_init_requests = Ritodetails.objects.filter(rito_id=init_requests.id).count()
    else:
        total_init_requests = 0
    
    pending_signatories = RitoSignatories.objects.filter(emp_id=current_emp_id,status=0)
    valid_pending_count = 0
    
    for sig in pending_signatories:
        rito_id = sig.rito_id
        current_signatory_type = sig.signatory_type
        
        previous_sigs = RitoSignatories.objects.filter(
            rito_id=rito_id,
            signatory_type__lt=current_signatory_type
        )
        
        if all(prev_sig.status == 1 for prev_sig in previous_sigs):
            valid_pending_count += 1
    
    return JsonResponse({'drafts': total_drafts,
                        'requests': total_requests,
                        'init_requests': total_init_requests,
                        'for_approval': valid_pending_count
                    })
    


def interval_rito_date_conflict(start_date, end_date, emp_id, rito_pk=None):
    conflict_query = Ritopeople.objects.filter(
        Q(detail__inclusive_from__lte=end_date, detail__inclusive_to__gte=start_date),
        Q(name_id=emp_id),
        ~Q(detail__rito__status=5)
    )

    # If rito_pk is provided, exclude it from the conflict check
    if rito_pk:
        conflict_query = conflict_query.exclude(detail_id=rito_pk)

    return conflict_query



@login_required
@permission_required('auth.travel_order')
def rito(request):
    if request.method == "POST":
        id = request.POST.get('draftid')
        if id == '' or id is None:
            check = Rito.objects.filter(Q(status=1) & Q(emp_id=request.session['emp_id'])).first()
        else:
            check = Rito.objects.filter(Q(id=id)).first()

        employee = request.POST.getlist('employee[]')
        employee = [emp.strip() for emp in employee if emp.strip()]

        if not employee:
            return JsonResponse({'error': 'No employees selected'}, status=400)
        from_datetime_str = request.POST.get('from')
        to_datetime_str = request.POST.get('to')
        
        try:
            from_datetime = datetime.fromisoformat(from_datetime_str)
            to_datetime = datetime.fromisoformat(to_datetime_str)
        except ValueError:
            return JsonResponse({'error': 'Invalid datetime format'}, status=400)

        employee_list = []
        for row in employee:
            id_number = re.split('\[|\]', row)
            
            # Check if we have the expected format [ID_NUMBER] NAME
            if len(id_number) < 2 or not id_number[1].strip():
                continue  # Skip invalid entries
            
            emp = Empprofile.objects.values('id').filter(id_number=id_number[1].strip()).first()
            
            if not emp:
                continue  # Skip if employee not found
            
            check_conflict = interval_rito_date_conflict(from_datetime, to_datetime, emp['id'])

            if check_conflict:
                employee_list.append({
                    'name': check_conflict.first().name.pi.user.first_name.upper(),
                    'text_date': 'specified dates' if from_datetime.date() != to_datetime.date() else 'specified date',
                    'to_number': [row.detail.rito.tracking_no if row.detail.rito.tracking_no else "drafted by {}".format(row.detail.rito.emp.pi.user.get_fullname.upper())
                                      for row in check_conflict],
                    'text_to': 'Travel Orders' if check_conflict.count() > 1 else 'Travel Order'
                })

        if employee_list:
            return JsonResponse({'error': True, 'conflict': employee_list})
        else:
            if check:
                check_confirmation = check_rito_confirmation_function(from_datetime, request.session['emp_id'])

                if check_confirmation:
                    return JsonResponse({'error': True, 'confirmation': True})

                details = Ritodetails(
                    rito_id=check.id,
                    place=request.POST.get('places'),
                    inclusive_from=from_datetime,
                    inclusive_to=to_datetime,
                    purpose=request.POST.get('purpose'),
                    expected_output=request.POST.get('expected_output'),
                    claims_id=request.POST.get('claims'),
                    mot_id=request.POST.get('mot'),
                    subject_id=request.POST.get('subject'),
                    lap=request.POST.get('lap') == '1') 
                
                details.save()

                employee = request.POST.getlist('employee[]')
                employee = [emp.strip() for emp in employee if emp.strip()]

                for row in employee:
                    id_number = re.split('\[|\]', row)
                    
                    if len(id_number) < 2 or not id_number[1].strip():
                        continue
                    
                    name = Empprofile.objects.values('id').filter(id_number=id_number[1].strip()).first()
                    if name:
                        Ritopeople.objects.create(
                            detail_id=details.id,
                            name_id=name['id'])
            else:
                config = PortalConfiguration.objects.filter(key_name='TRAVEL').first()

                current_counter = config.counter + 1
                current_year = datetime.now().year
                current_month = datetime.now().month

                tracking_no = 'TO-{}-{}-{}'.format(
                    str(current_year).zfill(4),
                    str(current_month).zfill(2),
                    '%04d' % int(current_counter)
                )

                to = Rito(
                    tracking_no=tracking_no,
                    status=1,
                    emp_id=request.session['emp_id'])

                to.save()

                PortalConfiguration.objects.filter(key_name='TRAVEL').update(
                    counter=F('counter') + 1
                )

                details = Ritodetails(
                    rito_id=to.id,
                    place=request.POST.get('places'),
                    inclusive_from=from_datetime,
                    inclusive_to=to_datetime,
                    purpose=request.POST.get('purpose'),
                    expected_output=request.POST.get('expected_output'),
                    claims_id=request.POST.get('claims'),
                    mot_id=request.POST.get('mot'),
                    subject_id=request.POST.get('subject'),
                    lap=request.POST.get('lap') == '1') 

                check_confirmation = check_rito_confirmation_function(from_datetime,
                                                                      request.session['emp_id'])
                if check_confirmation:
                    return JsonResponse({'error': True, 'confirmation': True})

                details.save()

                employee = request.POST.getlist('employee[]')
                employee = [emp.strip() for emp in employee if emp.strip()]
                
                for row in employee:
                    id_number = re.split('\[|\]', row)
                    
                    if len(id_number) < 2 or not id_number[1].strip():
                        continue
                    
                    name = Empprofile.objects.values('id').filter(id_number=id_number[1].strip()).first()
                    if name:
                        Ritopeople.objects.create(
                            detail_id=details.id,
                            name_id=name['id'])

            return JsonResponse({'data': "success"})

    context = {
        'claims': Claims.objects.filter(status=1).order_by('name'),
        'mot': Mot.objects.filter(status=1).order_by('name'),
        'subject': Subject.objects.filter(status=1).order_by('id'),
        'tab_parent': 'Travel Management',
        'tab_title': 'Travel Requests',
        'title': 'travel_management',
        'sub_title': 'travel',
        'divisions': Division.objects.order_by('div_name'),
        'sections': Section.objects.order_by('sec_name'),
    }
    return render(request, 'frontend/pas/rito/rito.html', context)





@login_required
@permission_required('auth.rito')
def edit_rito(request, pk):
    if request.method == "POST":
        employee = request.POST.getlist('employee[]')
        employee_list = []
        employee_list_not = []
        for row in employee:
            id_number = re.split('\[|\]', row)
            emp = Empprofile.objects.values('id').filter(id_number=id_number[1]).first()
            check = Ritopeople.objects.filter(detail__inclusive_from=request.POST.get('from'),
                                              detail__inclusive_to=request.POST.get('to'), name_id=emp['id']).first()

            if not check:
                check_conflict = interval_rito_date_conflict(request.POST.get('from'), request.POST.get('to'),
                                                             emp['id'])
                if check_conflict:
                    employee_list.append({
                        'name': check_conflict.first().name.pi.user.first_name.upper(),
                        'text_date': 'specified dates' if request.POST.get('from') != request.POST.get(
                            'to') else 'specified date',
                        'to_number': [row.detail.rito.tracking_no if row.detail.rito.tracking_no else "drafted by {}".format(row.detail.rito.emp.pi.user.get_fullname.upper())
                                      for row in check_conflict],
                        'text_to': 'Travel Orders' if check_conflict.count() > 1 else 'Travel Order'
                    })
                else:
                    employee_list_not.append(emp['id'])
                    

        if employee_list_not:
            for row in employee_list_not:
                check_conflict = interval_rito_date_conflict(request.POST.get('from'), request.POST.get('to'),
                                                             emp['id'])
                if check_conflict:
                    employee_list.append({
                        'name': check_conflict.first().name.pi.user.first_name.upper(),
                        'text_date': 'specified dates' if request.POST.get('from') != request.POST.get(
                            'to') else 'specified date',
                        'to_number': [row.detail.rito.tracking_no for row in check_conflict],
                        'text_to': 'Travel Orders' if check_conflict.count() > 1 else 'Travel Order'
                    })
                else:
                    Ritopeople.objects.create(
                        detail_id=pk,
                        name_id=row
                    )

        if not employee_list:
            Ritodetails.objects.filter(id=pk).update(
                place=request.POST.get('places'),
                inclusive_from=request.POST.get('from'),
                inclusive_to=request.POST.get('to'),
                purpose=request.POST.get('purpose'),
                expected_output=request.POST.get('expected_output'),
                claims_id=request.POST.get('claims'),
                mot_id=request.POST.get('mot')
            )

            return JsonResponse({'data': 'success'})
        else:
            return JsonResponse({'error': True, 'conflict': employee_list})

    context = {
        'rito': Ritodetails.objects.filter(id=pk).first(),
        'ritopeople': Ritopeople.objects.filter(detail_id=pk),
        'claims': Claims.objects.filter(status=1).order_by('name'),
        'mot': Mot.objects.filter(status=1).order_by('name'),
    }
    return render(request, 'frontend/pas/rito/edit_rito.html', context)


@csrf_exempt
@login_required
@permission_required('auth.rito')
def travel_undraft(request):
    Rito.objects.filter(emp_id=request.session['emp_id'], status=1).update(status=4)

    Rito.objects.annotate(hash=SHA1('id')).filter(hash=request.POST.get('pk')).update(
        status=1
    )
    return JsonResponse({'data': 'success'})


@csrf_exempt
@login_required
@permission_required('auth.rito')
def delete_rito(request):
    Ritodetails.objects.filter(id=request.POST.get('id')).delete()
    Ritopeople.objects.filter(detail_id=request.POST.get('id')).delete()
    return JsonResponse({'data': 'success'})


@login_required
@permission_required('auth.rito')
def delete_drafts(request, id):
    ritodetails = Ritodetails.objects.filter(rito_id=id)
    for row in ritodetails:
        Ritopeople.objects.filter(detail_id=row.id).delete()
    Ritodetails.objects.filter(rito_id=id).delete()
    Rito.objects.filter(id=id).delete()
    return redirect('rito')


@login_required
@permission_required('auth.rito')
def submit_rito(request):
    if request.POST.get('draftid2') == '':
        rito = Rito.objects.filter(Q(status=1) & Q(emp_id=request.session['emp_id']))
    else:
        rito = Rito.objects.filter(Q(id=request.POST.get('draftid2')))

    if rito:
        tracking_no = ''
        if not rito.first().tracking_no:
            config = PortalConfiguration.objects.filter(key_name='TRAVEL').first()

            current_counter = config.counter + 1
            current_year = datetime.now().year
            current_month = datetime.now().month

            tracking_no = 'TO-{}-{}-{}'.format(
                str(current_year).zfill(4),
                str(current_month).zfill(2),
                '%04d' % int(current_counter)
            )

            rito.update(
                tracking_no=tracking_no,
                status=2,
                date=datetime.now())

            PortalConfiguration.objects.filter(key_name='TRAVEL').update(
                counter=F('counter') + 1
            )

            tracking_no = tracking_no
        else:
            tracking_no = rito.first().tracking_no

            rito.update(
                status=2,
                date=datetime.now())
        # Save points for RITO
        gamify(14, request.session['emp_id'])

        return JsonResponse({'data': tracking_no})
    else:
        return JsonResponse({'error': "Sorry, it seems like you have empty RITO's."})


@login_required
@csrf_exempt
@permission_required('auth.rito')
def draft_rito(request):
    if request.POST.get('id') == '' or request.POST.get('id') is None:
        rito = Rito.objects.filter(Q(status=1) & Q(emp_id=request.session['emp_id']))
    else:
        rito = Rito.objects.filter(id=request.POST.get('id'))

    if rito:
        rito.update(
            status=4,
            date=datetime.now())
        return JsonResponse({'data': "success"})
    else:
        return JsonResponse({'error': "Sorry, it seems like you have empty RITO's."})



@login_required
@permission_required('auth.rito')
def print_rito(request, pk):
    rito = Rito.objects.filter(id=pk).first()
    if not rito:
        raise Http404("RITO record not found.")

    config = PortalConfiguration.objects.filter(key_name='TR INCHARGE').first()
    emp = Empprofile.objects.filter(id=request.session['emp_id']).first()
    requested_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type=0).first()
    noted_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type=1).first()
    approved_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type=2).first()


    section_head = Section.objects.filter(id=emp.section_id).first()
    division_head = Division.objects.filter(id=section_head.div_id).first()
    designation = Designation.objects.filter(name='Regional Director').first()

    rito_details = Ritodetails.objects.filter(rito_id = rito.id)
    paginator = Paginator(rito_details,20)
    pagination  = paginator.num_pages


    context = {
        'rito': Ritodetails.objects.filter(rito_id=rito.id),
        'officer_in_charge': config.key_acronym.split(', ') if config else [],
        'name': rito,
        'date': datetime.now(),
        'requested_by': requested_by,
        'noted_by': noted_by,
        'approved_by': approved_by,
        'section_head': section_head,
        'division_head': division_head,
        'designation': designation,
        'pagination': math.ceil(float(pagination) / 20),

    }

    return render(request, 'frontend/pas/rito/print_rito.html', context)



@login_required
@csrf_exempt
@permission_required('auth.rito')
def get_vehicle_request_token(request):
    url = "https://crg-finance-svr.entdswd.local/gstracking/api/v2/printrequest"
    body = {'id': request.POST.get('id') }
    headers = {'KEY': 'aee465aff8944cce528d297b601b273f871f65b75d9f3bdface0bfa284953851',
               'content-type': 'application/json'}

    r = requests.post(url, data=json.dumps(body), headers=headers, verify=False)
    return JsonResponse({'data': r.text.replace('"', '')})


@login_required
@csrf_exempt
@permission_required('auth.rito')
def cancel_travel_request(request):
    if request.method == 'POST':
        Rito.objects.filter(id=request.POST.get('id')).update(status=5)
        return JsonResponse({'data': 'success'})


@login_required
@permission_required('auth.rito')
def attachment_update(request, tracking_no):
    check_merge = Rito.objects.filter(tracking_merge=tracking_no)
    rito = Rito.objects.filter(tracking_no=tracking_no).first()

    if check_merge:
        rito_attachment = RitoAttachment.objects.filter(rito_id=check_merge.first().id)
    else:
        rito_attachment = RitoAttachment.objects.filter(rito_id=rito.id)

    if request.method == "POST":
        file = request.FILES.get('file')
        attachment_type = request.POST.get('attachment_type')
        if check_merge:
            rito_id = check_merge.first().id
        else:
            rito_id = rito.id

        if rito_attachment.count() > 0:
            rito_attachment.update(file=file, type=attachment_type)
        else:
            RitoAttachment.objects.create(rito_id=rito_id, file=file, type=attachment_type)

        return JsonResponse({'data': 'success', 'tracking_no': tracking_no})

    context = {
        'rito': check_merge.first() if check_merge else rito,
        'attachment': rito_attachment.first(),
        'management': True,
        'title': 'to',
        'sub_title': 'rito'
    }
    return render(request, 'frontend/pas/rito/attachment.html', context)


@login_required
@permission_required('auth.rito')
def view_tracking_details(request, pk):
    rito = Rito.objects.filter(id=pk).first()
    context = {
        'tracking': rito
    }
    return render(request, 'frontend/pas/rito/tracking_details.html', context)


@login_required
@permission_required('auth.rito')
def set_rito_signatories(request, pk, type=1):
    if request.method == "POST":
        self_approval = request.POST.get('self_approval')
        requested_by = request.POST.get('requested_by')
        noted_by = request.POST.get('noted_by')
        approved_by = request.POST.get('approved_by')
        rams_approval = request.POST.get('rams_approval')

        def extract_emp(field_value):
            if not field_value:
                return None
            parts = re.split(r'\[|\]', field_value)
            if len(parts) > 1 and parts[1]:
                return Empprofile.objects.filter(id_number=parts[1]).first()
            return None

        def save_or_update_signatory(emp, rito_id, sig_type):
            if not emp:
                return
            existing = RitoSignatories.objects.filter(rito_id=rito_id, signatory_type=sig_type)
            if existing.exists():
                existing.update(emp_id=emp.id)
            else:
                RitoSignatories.objects.create(
                    rito_id=rito_id,
                    emp_id=emp.id,
                    signatory_type=sig_type,
                    status=0
                )

        # extract employees
        self_emp = extract_emp(self_approval)
        req_emp = extract_emp(requested_by)
        note_emp = extract_emp(noted_by)
        appr_emp = extract_emp(approved_by)
        rams_emp = extract_emp(rams_approval)

        # save signatories
        save_or_update_signatory(self_emp, pk, "0")   # self
        save_or_update_signatory(req_emp, pk, "1")    # requested
        save_or_update_signatory(note_emp, pk, "2")   # noted
        save_or_update_signatory(appr_emp, pk, "3")   # approved
        save_or_update_signatory(rams_emp, pk, "4")   # RAMS

        return JsonResponse({'success': True})

    # --------------------------------
    # GET logic for displaying form
    # --------------------------------
    emp = Empprofile.objects.filter(id=request.session['emp_id']).first()
    section_head = None
    division_head = None
    is_division_request = False

    if emp:
        # Check if employee has designation
        designation_name = None
        if hasattr(emp, 'designation') and emp.designation:
            designation_name = emp.designation.name if hasattr(emp.designation, 'name') else str(emp.designation)
        
        # Check if the designation is "Division AA" FIRST, regardless of section
        if designation_name and designation_name == "Division AA":
            is_division_request = True
            # Get division info if available
            if emp.section:
                section_head = Section.objects.filter(id=emp.section_id).first()
                division_head = section_head.div if section_head else None
            else:
                divisions = Division.objects.all()
                if divisions.exists():
                    division_head = divisions.first()
        elif emp.section:  # normal employee with section
            section_head = Section.objects.filter(id=emp.section_id).first()
            division_head = section_head.div if section_head else None

    # Designation & RAMS
    designation = Designation.objects.filter(name='Regional Director').first()
    rams = Empprofile.objects.filter(
        position__name="Administrative Assistant III",
        section__sec_name="Records and Archives Management Section"
    ).first()

    # signatories (if existing)
    self_approval = RitoSignatories.objects.filter(rito_id=pk, signatory_type="0").first()
    requested_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type="1").first()
    noted_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type="2").first()
    approved_by = RitoSignatories.objects.filter(rito_id=pk, signatory_type="3").first()
    rams_approval = RitoSignatories.objects.filter(rito_id=pk, signatory_type="4").first()

    context = {
        'signatories': RitoSignatories.objects.filter(rito_id=pk).order_by('signatory_type'),
        'section_head': section_head,
        'division_head': division_head,
        'designation': designation,
        'rams': rams,
        'self_approval': self_approval,
        'requested_by': requested_by,
        'noted_by': noted_by,
        'approved_by': approved_by,
        'rams_approval': rams_approval,
        'type': type,
        'is_division_request': is_division_request,
    }
    return render(request, 'frontend/pas/rito/modals/set_signatories_content.html', context)




@login_required
@permission_required('auth.travel_order')
def approved_rito_signatories(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    signatory_id = request.POST.get('signatory_id')
    password = request.POST.get('p12_password')

    if not signatory_id or not password:
        return JsonResponse({'error': 'Signatory ID and password are required.'}, status=400)

    try:
        signatory = RitoSignatories.objects.select_related('rito', 'emp__pi__user').get(id=signatory_id)
        print(f"Found signatory: {signatory.id}")
    except RitoSignatories.DoesNotExist:
        print(f"Signatory not found: {signatory_id}")
        return JsonResponse({'error': 'Signatory not found.'}, status=404)
    except Exception as e:
        print(f"Error finding signatory: {e}")
        return JsonResponse({'error': 'Database error occurred.'}, status=500)

    # Check authorization
    session_emp_id = request.session.get('emp_id')
    if session_emp_id != signatory.emp_id:
        print(f"Authorization failed: session_emp_id={session_emp_id}, signatory.emp_id={signatory.emp_id}")
        return JsonResponse({'error': 'You are not authorized to approve this request.'}, status=403)

    if signatory.status == 1:
        return JsonResponse({'error': 'This travel request has already been approved by you.'}, status=400)

    # Validate certificate/password
    try:
        validation = validate_p12_certificate(signatory.emp_id, password)
        print(f"Certificate validation result: {validation}")
        if not validation['valid']:
            return JsonResponse({'error': validation['error']}, status=400)
    except Exception as e:
        print(f"Certificate validation error: {e}")
        return JsonResponse({'error': 'Certificate validation failed.'}, status=500)

    # Check if previous approvers have approved first
    try:
        # Convert signatory_type to int if it's a string
        current_signatory_type = int(signatory.signatory_type) if signatory.signatory_type else 0
        
        previous_pending = RitoSignatories.objects.filter(
            rito_id=signatory.rito_id,
            signatory_type__lt=current_signatory_type,
            status=0
        ).exists()
        
        if previous_pending:
            return JsonResponse({'error': 'Previous approvers must approve first.'}, status=400)
    except Exception as e:
        print(f"Error checking previous approvers: {e}")
        return JsonResponse({'error': 'Error checking approval sequence.'}, status=500)

    # Update signatory status
    try:
        signatory.status = 1
        signatory.date = timezone.now()
        signatory.save(update_fields=['status', 'date'])
        print(f"Signatory updated successfully")
    except Exception as e:
        print(f"Error updating signatory: {e}")
        return JsonResponse({'error': 'Error updating approval status.'}, status=500)

    has_p12 = validation.get('has_p12', False)

    # Get signature image
    esignature = None
    try:
        signature_record = Signature.objects.filter(emp_id=signatory.emp_id).first()
        if signature_record and signature_record.signature_img:
            with open(signature_record.signature_img.path, 'rb') as img_file:
                esignature = base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error getting signature image: {e}")

    try:
        if hasattr(signatory.emp, 'pi') and hasattr(signatory.emp.pi, 'user'):
            user = signatory.emp.pi.user
            emp_name = f"{user.first_name} {user.middle_name[0] + '.' if user.middle_name else ''} {user.last_name}"
        else:
            emp_name = 'Unknown'
    except Exception as e:
        print(f"Error getting employee name: {e}")
        emp_name = 'Unknown'

    try:
        if signature_record:
            signature_record.is_p12_signed = True
            signature_record.save()
    except Exception as e:
        print(f"Error updating signature record: {e}")

    print("Approval completed successfully")
    return JsonResponse({
        'success': True,
        'message': 'Travel request approved successfully.',
        'signature_img': esignature,
        'signatory_id': signatory_id,
        'signatory_type': current_signatory_type,
        'emp_name': emp_name,
        'date_approved': signatory.date.strftime('%B %d, %Y %I:%M %p') if signatory.date else None,
        'has_p12': has_p12
    })



@csrf_exempt
@login_required
def sign_uploaded_travel_pdf(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    uploaded_pdf = request.FILES.get('pdf_file')
    signature_positions_json = request.POST.get('signature_positions')
    
    if not uploaded_pdf:
        return JsonResponse({'error': 'Missing PDF file'}, status=400)

    # Parse signature positions
    dynamic_positions = None
    target_page = 0  # Default to first page (0-indexed)
    total_pages = 1
    
    if signature_positions_json:
        try:
            import json
            dynamic_positions = json.loads(signature_positions_json)
            print(f"Received dynamic signature positions: {dynamic_positions}")
            
            if 'total_pages' in dynamic_positions:
                total_pages = dynamic_positions['total_pages']
            
            if 'rd_signature' in dynamic_positions:
                rd_sig = dynamic_positions['rd_signature']
                if 'page_number' in rd_sig:
                    target_page = rd_sig['page_number'] - 1
                    print(f"Target page for signature: {target_page + 1} (0-indexed: {target_page}) of {total_pages} total pages")
                    
        except Exception as e:
            print(f"Error parsing signature positions: {e}")
            import traceback
            traceback.print_exc()

    # Get current user's employee ID
    emp_id = None
    if hasattr(request.user, 'empprofile'):
        emp_id = request.user.empprofile.id
    elif request.session.get('emp_id'):
        emp_id = request.session.get('emp_id')
    else:
        return JsonResponse({'error': 'Unable to identify current user'}, status=400)

    try:
        rito = Rito.objects.filter(pk=pk).first()
        if not rito:
            return JsonResponse({'error': 'Travel order not found'}, status=404)

        # Check authorization
        is_requester = rito.emp_id == emp_id
        is_signatory = RitoSignatories.objects.filter(rito_id=pk, emp_id=emp_id).exists()
        
        if not (is_requester or is_signatory):
            return JsonResponse({'error': 'You are not authorized to download this travel order'}, status=403)

        # Get all approved signatories
        approved_signatories = RitoSignatories.objects.filter(
            rito_id=pk, 
            status=1,
            date__isnull=False
        ).select_related('emp').order_by('date')  
        
        if not approved_signatories.exists():
            uploaded_pdf.seek(0)
            response = HttpResponse(uploaded_pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="travel_order.pdf"'
            return response

        current_pdf_buffer = io.BytesIO(uploaded_pdf.read())
        signature_count = 0
        
        # Apply signatures from all approved signatories
        for signatory in approved_signatories:
            sig_record = Signature.objects.filter(emp_id=signatory.emp.id).first()
            
            if sig_record and sig_record.p12_file:
                try:
                    signatory_password = None
                    if sig_record.p12_password_enc:
                        signatory_password = decrypt_text(sig_record.p12_password_enc)
                    else:
                        print(f"No stored password for signatory {signatory.emp.id}, skipping...")
                        continue
                    
                    validation = validate_p12_certificate(signatory.emp.id, signatory_password)
                    if not validation['valid']:
                        print(f"Invalid certificate for signatory {signatory.emp.id}: {validation['error']}")
                        continue
                    
                    # Pass all required parameters including target_page
                    current_pdf_buffer = multiple_travel_signatories(
                        current_pdf_buffer,
                        sig_record,
                        signatory_password,
                        signatory,
                        signature_count,
                        dynamic_positions,
                        target_page  # This is the key parameter!
                    )
                    signature_count += 1
                    
                except Exception as e:
                    print(f"Could not apply signature for {signatory.emp.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            # else:
            #     print(f"No P12 certificate found for signatory {signatory.emp.id}")

        current_pdf_buffer.seek(0)
        
        filename = f"Regional_Special_Order_{rito.tracking_no or rito.tracking_merge}.pdf"
        response = HttpResponse(current_pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in sign_uploaded_travel_pdf: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Signing failed: {str(e)}'}, status=500)
    
    

def get_travel_context_multi(pk, request):
    rito = Rito.objects.filter(pk=pk).select_related('emp__pi__user', 'emp__section').first()
    
    if not rito:
        return {}
    signatories = RitoSignatories.objects.filter(rito_id=rito.id).select_related('emp__pi__user').order_by('signatory_type')

    signatories_data = {}
    
    for s in signatories:
        s.esignature = None
        s.validation_stamp_b64 = None
        s.has_p12 = False
        s.signature_img = None  # ADD THIS LINE
        
        if s.status == 1 and s.date is not None:
            try:
                sig_record = Signature.objects.filter(emp_id=s.emp.id).first()
                if sig_record:
                    s.has_p12 = sig_record.p12_file and os.path.exists(sig_record.p12_file.path)
                    
                    if sig_record.signature_img:
                        with open(sig_record.signature_img.path, 'rb') as f:
                            signature_data = base64.b64encode(f.read()).decode('utf-8')
                            s.esignature = signature_data
                            s.signature_img = signature_data  # ADD THIS LINE
                        
                        signed_date = s.date.strftime('%Y-%m-%d %H:%M')
                        cert_name = f"{s.emp.pi.user.first_name} {s.emp.pi.user.last_name}"
                        
                        s.validation_stamp_b64 = generate_validated_signature_stamp(
                            sig_record, 
                            signed_date, 
                            cert_name
                        )
                        
                        role_mapping = {
                            0: 'requester',
                            1: 'section_head', 
                            2: 'division_chief',
                            3: 'approving_authority',
                            4: 'hr_officer'
                        }
                        
                        role_key = role_mapping.get(s.signatory_type)
                        if role_key:
                            signatories_data[role_key] = s.emp
                        
                        # print(f"Loaded signature for approved signatory: {cert_name} (Type: {s.signatory_type})")
                        
            except Exception as e:
                print(f"Error loading signature for emp {s.emp.id}: {e}")
      

    context = {
        'rito': rito,
        'signatories': signatories,
        'signatories_data': signatories_data,
        'date': datetime.now().strftime('%B %d, %Y'),
    }

    return context


@login_required
def download_signed_travel_multi(request, pk):
    rito = Rito.objects.filter(pk=pk).first()
    if not rito:
        return HttpResponse("Travel order not found.", status=404)

    emp_id = None
    if hasattr(request.user, 'empprofile'):
        emp_id = request.user.empprofile.id
    elif request.session.get('emp_id'):
        emp_id = request.session.get('emp_id')

    if not emp_id:
        return HttpResponse("Unable to identify current user.", status=400)

    is_requester = rito.emp_id == emp_id
    is_signatory = RitoSignatories.objects.filter(rito_id=rito.id, emp_id=emp_id).exists()
    
    if not (is_requester or is_signatory):
        return HttpResponse("You are not authorized to download this document.", status=403)

    try:
        context = get_travel_context_multi(pk, request)
        html_content = render_to_string( 'backend/pas/travel_order/generate_to.html',  context, request=request  )

        from weasyprint import HTML
        pdf_buffer = io.BytesIO()
        HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf(
            target=pdf_buffer
        )

        approved_signatories = RitoSignatories.objects.filter(
            rito_id=rito.id, 
            status=1,  
            date__isnull=False  
        ).select_related('emp').order_by('date') 

        if not approved_signatories.exists():
            pdf_buffer.seek(0)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="travel_order.pdf"'
            return response

        # Apply signatures to PDF
        current_pdf_buffer = io.BytesIO(pdf_buffer.getvalue())
        signature_count = 0
        
        for index, signatory in enumerate(approved_signatories):
            signature_record = Signature.objects.filter(emp_id=signatory.emp.id).first()
            
            if signature_record and signature_record.p12_file:
                try:
                    # Get the stored encrypted password for this signatory
                    signatory_password = None
                    if signature_record.p12_password_enc:
                        signatory_password = decrypt_text(signature_record.p12_password_enc)
                    else:
                        print(f"No stored password for signatory {signatory.emp.id}, skipping...")
                        continue
                    
                    # Validate certificate
                    validation = validate_p12_certificate(signatory.emp.id, signatory_password)
                    if validation['valid']:
                        print(f"Applying signature {signature_count + 1} for {signatory.emp.pi.user.get_fullname}")
                        
                        # Apply signature using travel-specific function
                        new_pdf_buffer = multiple_travel_signatories(
                            current_pdf_buffer, 
                            signature_record, 
                            signatory_password, 
                            signatory,
                            signature_count  
                        )
                        current_pdf_buffer = new_pdf_buffer
                        signature_count += 1
                        
                except Exception as e:
                    print(f"Could not apply signature for {signatory.emp.id}: {e}")
                    continue

        current_pdf_buffer.seek(0)
        filename = f"signed_travel_order_{signature_count}_sigs.pdf"
        response = HttpResponse(current_pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in download_signed_travel_multi: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f"Error generating signed PDF: {str(e)}", status=500)





@login_required
@permission_required('auth.rito')
def disapproved_rito_signatories(request):
    if request.method == "POST":
        id = request.POST.get('id')
        RitoSignatories.objects.filter(id=id).update(status=2)
        return JsonResponse({'success': True})
    
    

def check_rito_authenticity(request, pk):
    rito = Rito.objects.filter(id=pk).first()
    signatories = RitoSignatories.objects.filter(rito_id=pk).select_related('emp__pi__user').order_by('signatory_type')
    workflow_count = signatories.filter(status=1).count() 
    total_signatories = signatories.count()

    context = {
        'rito': rito,
        'signatories': signatories,
        'workflow_count': workflow_count,
        'total_signatories': total_signatories
    }
    return render(request, 'frontend/pas/rito/rito_authenticity.html', context)


@require_http_methods(["GET"])
def employees_by_section(request):
    section_id = request.GET.get('section_id')
    
    if not section_id:
        return JsonResponse({'error': 'Section ID is required'}, status=400)
    
    try:
        employees = Empprofile.objects.filter( section_id=section_id ).select_related('pi__user').order_by('pi__user__first_name')
        employee_list = []
        for emp in employees:
            full_name = f"[{emp.id_number}] {emp.pi.user.get_fullname.upper()}"
            employee_list.append(full_name)
        
        return JsonResponse({ 'success': True,'employees': employee_list})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@require_http_methods(["GET"])
def employees_by_division(request):
    division_id = request.GET.get('division_id')
    
    if not division_id:
        return JsonResponse({'error': 'Division ID is required'}, status=400)
    
    try:
        employees = Empprofile.objects.filter( section__div_id=division_id).select_related('pi__user').order_by('pi__user__first_name')
        employee_list = []
        for emp in employees:
            full_name = f"[{emp.id_number}] {emp.pi.user.get_fullname.upper()}"
            employee_list.append(full_name)
        
        return JsonResponse({'success': True, 'employees': employee_list })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)