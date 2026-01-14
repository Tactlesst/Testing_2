import os
import io
import re
import json
import base64
import threading
from datetime import datetime, date

from dateutil.parser import parse
from PIL import Image
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F, Exists, OuterRef, IntegerField, ExpressionWrapper
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from weasyprint import HTML, CSS
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509

# Internal imports
from api.wiserv import send_notification
from backend.libraries.leave.models import (
    LeaveSubtype, LeaveCredits, LeaveSpent, LeaveApplication,
    LeavespentApplication, LeavePermissions, LeaveRandomDates,
    CTDORequests, CTDORandomDates, LeavePrintLogs, CTDOPrintLogs,
    CTDOBalance, CTDOUtilization, CTDOActualBalance, CTDOHistoryBalance,
    CTDOCoc, LeaveCompenattachment
)
from backend.models import Section, Division, Designation, Empprofile, AuthUserUserPermissions, AuthUser
from backend.templatetags.tags import force_token_decryption
from backend.views import generate_serial_string
from frontend.models import PortalConfiguration
from frontend.templatetags.tags import gamify
from backend.libraries.leave.models import Signature, LeaveSignatories
from frontend.leave.crypto import decrypt_text
from frontend.leave.utils import get_leave_context_multi,multiple_signatories,get_signatory_password,generate_signature_stamp


# pyHanko signing
from pyhanko.sign import signers
from pyhanko.sign.signers import PdfSigner, PdfSignatureMetadata
from pyhanko.sign.fields import SigFieldSpec, append_signature_field
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.images import PdfImage
from pyhanko.stamp import StaticStampStyle

import logging

# Initialize logger
logger = logging.getLogger(__name__)

@login_required
def leave_application(request):
    if request.method == "POST":
        leavesubtype_id = request.POST.get('leavesubtype')
        
        if leavesubtype_id:
            try:
                selected_subtype = LeaveSubtype.objects.get(id=leavesubtype_id)
                if selected_subtype.leavetype_id == 4:  # Compensatory leave
                    try:
                        leave_credit = LeaveCredits.objects.get(
                            emp_id=request.session['emp_id'], 
                            leavetype_id=4
                        )
                        if leave_credit.leave_total <= 0:
                            return JsonResponse({
                                'error': 'insufficient_credits',
                                'message': f'You don\'t have enough compensatory leave credits. Available credits: {leave_credit.leave_total}',
                                'available_credits': float(leave_credit.leave_total)
                            }, status=400)
                    except LeaveCredits.DoesNotExist:
                        return JsonResponse({
                            'error': 'no_credits',
                            'message': 'You don\'t have any compensatory leave credits available. Please contact your Administrator',
                            'available_credits': 0
                        }, status=400)
            except LeaveSubtype.DoesNotExist:
                return JsonResponse({
                    'error': 'invalid_leave_type',
                    'message': 'Invalid leave type selected.'
                }, status=400)
        
        leavespent_check = request.POST.get('leavespent_check')
        uploaded_file = request.FILES.get('file')

        if leavespent_check:
            leavespent_specify = request.POST.get('leavespent_specify' + leavespent_check)
        else:
            leavespent_specify = request.POST.get('leavespent_specify')

        lasttrack = LeaveApplication.objects.filter(status=0).last()
        track_num = generate_serial_string(lasttrack.tracking_no) if lasttrack else \
                    generate_serial_string(None, 'LV')

        l_application = LeaveApplication(
            tracking_no=track_num,
            leavesubtype_id=leavesubtype_id,
            start_date=request.POST.get('start_date') or None,
            end_date=request.POST.get('end_date') or None,
            reasons=request.POST.get('reasons'),
            remarks=request.POST.get('remarks') or None,
            date_of_filing=datetime.now(),
            status=0,
            emp_id=request.session['emp_id'],
            file=uploaded_file if uploaded_file else None 
        )

        if not l_application.get_subtype:
            return JsonResponse({'error': 'File is required for this leave type.'}, status=400)

        l_application.save()

        # save leavespent
        LeavespentApplication.objects.create(
            leaveapp_id=l_application.id,
            leavespent_id=leavespent_check,
            status=1 if leavespent_check != "" else None,
            specify=leavespent_specify
        )

        random_dates = request.POST.getlist('dates[]')
        if random_dates and random_dates[0] != '':
            for row in random_dates:
                LeaveRandomDates.objects.create(
                    leaveapp_id=l_application.id,
                    date=row
                )

        return JsonResponse({'data': 'success', 'tracking_no': track_num})

    if request.GET.get('format') == 'datatables':
        leave_applications = LeaveApplication.objects.all()
        data = []
        for leave_application in leave_applications:
            data.append({
                'id': leave_application.id,
                'tracking_no': leave_application.tracking_no,
                'leavesubtype_name': leave_application.leavesubtype.name,
                'inclusive_dates': leave_application.get_inclusive(),
                'date_of_filing': leave_application.date_of_filing,
                'status': leave_application.status,
                'file': leave_application.file.url if leave_application.file and leave_application.file.name != 'leave/default.pdf' else None,
                'file_status': 'Attached' if leave_application.file and leave_application.file.name != 'leave/default.pdf' else 'Not Attached',
            })
        return JsonResponse(data, safe=False)

    emp = Empprofile.objects.filter(id=request.session['emp_id']).first()
    context = {
        'emp': emp,
        'leavesubtype': LeavePermissions.objects.filter(
            empstatus_id=emp.empstatus_id,
            leavesubtype__status=1
        ).order_by('leavesubtype__name'),
        'leave_credits': LeaveCredits.objects.filter(emp_id=request.session['emp_id']),
        'date': datetime.now(),
        'tab_parent': 'Leave Management',
        'tab_title': 'Leave Requests',
        'title': 'leave_management',
        'sub_title': 'user_leave',
    }
    return render(request, 'frontend/leave/leave_application_new.html', context)


@login_required
def edit_leave_application(request, pk):
    if request.method == "POST":
        leavespent_check = request.POST.get('leavespent_check')

        if leavespent_check:
            leavespent_specify = request.POST.get('leavespent_specify' + leavespent_check)
        else:
            leavespent_specify = request.POST.get('leavespent_specify')

        leave_spent = LeavespentApplication.objects.filter(leaveapp_id=pk).first()

        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        LeaveApplication.objects.filter(id=pk).update(
            leavesubtype_id=request.POST.get('leavesubtype'),
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            reasons=request.POST.get('reasons'),
            remarks=None if not request.POST.get('remarks') else request.POST.get('remarks'),
            date_of_filing=request.POST.get('date_of_filing') if request.POST.get('date_of_filing') else F('date_of_filing'),
            status=0,
        )

        LeavespentApplication.objects.filter(id=leave_spent.id).update(
            leavespent_id=leavespent_check,
            status=1 if leavespent_check != "" else None,
            specify=leavespent_specify
        )

        random_dates = request.POST.getlist('dates[]')
        if random_dates and random_dates[0] != '':
            custom_dates = [str(row.date) for row in LeaveRandomDates.objects.filter(leaveapp_id=pk)]
            comparison = list(set(random_dates) - set(custom_dates))

            for row in comparison:
                LeaveRandomDates.objects.create(
                    leaveapp_id=pk,
                    date=row
                )

            LeaveRandomDates.objects.filter(~Q(date__in=random_dates), Q(leaveapp_id=pk)).delete()

        return JsonResponse({'data': 'success', 'tracking_no': leave_spent.leaveapp.tracking_no})

    permission = AuthUserUserPermissions.objects.filter(
        user_id=request.user.id,
        permission_id=36
    )
    superadmin = AuthUser.objects.filter(id=request.user.id).first()
    if permission or superadmin.is_superuser:
        emp = Empprofile.objects.filter(id=1).first()
    else:
        emp = Empprofile.objects.filter(id=request.session['emp_id']).first()

    context = {
        'leavesubtype': LeavePermissions.objects.filter(empstatus_id=emp.empstatus_id),
        'leave_random_dates': LeaveRandomDates.objects.filter(leaveapp_id=pk),
        'leave': LeavespentApplication.objects.filter(leaveapp_id=pk).first(),
        'leave_app': LeaveApplication.objects.filter(id=pk).first(),
        'pk': pk,
    }
    return render(request, 'frontend/leave/edit_leave_application.html', context)

@login_required
@csrf_exempt
def cancel_leave(request):
    if request.method == "POST":
        LeaveApplication.objects.filter(id=request.POST.get('id'), emp_id=request.session['emp_id']).update(
            status=2
        )
        return JsonResponse({'data': 'success'})


@login_required
@csrf_exempt
def get_leavespent(request):
    leave_id = request.POST.get('id')
    if not leave_id:
        return JsonResponse({'error': 'Leave subtype ID is required'}, status=400)

    leave_spent = LeaveSpent.objects.filter(leavesubtype_id=leave_id, status=1)
    leave_subtype = LeaveSubtype.objects.filter(id=leave_id).first()
    data = [dict(id=row.id, name=row.name, is_specify=row.is_specify) for row in leave_spent]
    return JsonResponse({'data': data, 'has_reason': leave_subtype.has_reason, 'remarks_text': leave_subtype.remarks_text,
                         'with_days': leave_subtype.with_days})





@login_required
def approved_leave_signatories(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    signatory_id = request.POST.get('id')
    password = request.POST.get('p12_password')

    if not signatory_id or not password:
        return JsonResponse({'error': 'Signatory ID and password are required.'}, status=400)

    try:
        signatory = LeaveSignatories.objects.select_related('leave', 'emp__pi__user').get(id=signatory_id)
    except LeaveSignatories.DoesNotExist:
        return JsonResponse({'error': 'Signatory not found.'}, status=404)

    if request.session.get('emp_id') != signatory.emp_id:
        return JsonResponse({'error': 'You are not authorized to approve this request.'}, status=403)

    if signatory.status == 1:
        return JsonResponse({'error': 'This leave request has already been approved by you.'}, status=400)
    


    validation = validate_p12_certificate(signatory.emp_id, password)
    if not validation['valid']:
        return JsonResponse({'error': validation['error']}, status=400)

    if LeaveSignatories.objects.filter(leave_id=signatory.leave_id,
                                        signatory_type__lt=signatory.signatory_type,
                                        status=0
    ).exists():
        return JsonResponse({'error': 'Previous approvers must approve first.'}, status=400)

    signatory.status = 1
    signatory.date = timezone.now()
    signatory.save(update_fields=['status', 'date'])
    
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

    # Get employee name
    try:
        if hasattr(signatory.emp, 'pi') and hasattr(signatory.emp.pi, 'user'):
            user = signatory.emp.pi.user
            emp_name = f"{user.first_name} {user.middle_name[0] + '.' if user.middle_name else ''} {user.last_name}"
        else:
            emp_name = 'Unknown'
    except:
        emp_name = 'Unknown'
        
    signatory.is_p12_signed = True  # Mark this as P12 signed
    signatory.status = 1
    signatory.date = timezone.now()
    signatory.save()
    
    signature = Signature.objects.filter(emp_id=signatory.emp.id).first()
    if signature:
        signature.is_p12_signed = True
        signature.save()

    return JsonResponse({
        'success': True,
        'message': 'Leave approved successfully.',
        'signature_img': esignature,
        'signatory_id': signatory_id,
        'signatory_type': signatory.signatory_type,
        'emp_name': emp_name,
        'date_approved': signatory.date.strftime('%B %d, %Y %I:%M %p') if signatory.date else None,
        'has_p12': has_p12  # Add this line
    })





def validate_p12_certificate(emp_id, password):
    try:
        signature = Signature.objects.filter(emp_id=emp_id).first()
        
        if not signature:
            return {
                'valid': False,
                'error': 'No signature profile found for your account. Please contact your administrator.',
                'error_type': 'signature_not_found'
            }
        
        # Check if user has p12 certificate
        if signature.p12_file and os.path.exists(signature.p12_file.path):
            # Validate using p12 certificate
            try:
                with open(signature.p12_file.path, 'rb') as p12_file:
                    p12_data = p12_file.read()
                    
                from cryptography.hazmat.primitives import serialization
                serialization.pkcs12.load_key_and_certificates(
                    p12_data, 
                    password.encode('utf-8')
                )
                
                return {
                    'valid': True,
                    'error': None,
                    'error_type': None,
                    'has_p12': True
                }
                
            except ValueError:
                return {
                    'valid': False,
                    'error': 'Invalid certificate password. Please check your password and try again.',
                    'error_type': 'p12_password_invalid'
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Error validating certificate: {str(e)}',
                    'error_type': 'p12_validation_error'
                }
        else:
            # No p12 certificate - validate using stored password
            try:
                if signature.p12_password_enc:
                    stored_password = decrypt_text(signature.p12_password_enc)
                    if stored_password == password:
                        return {
                            'valid': True,
                            'error': None,
                            'error_type': None,
                            'has_p12': False
                        }
                    else:
                        return {
                            'valid': False,
                            'error': 'Invalid authentication password.',
                            'error_type': 'password_mismatch'
                        }
                else:
                    return {
                        'valid': False,
                        'error': 'No authentication method found. Please re-upload your signature.',
                        'error_type': 'no_auth_method'
                    }
                    
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Error validating password: {str(e)}',
                    'error_type': 'password_validation_error'
                }
            
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error accessing signature profile: {str(e)}',
            'error_type': 'signature_access_error'
        }


@login_required
def print_leaveapp(request, pk):
    leave = LeaveApplication.objects.filter(id=pk).first()
    if not leave:
        return HttpResponse("Leave application not found.", status=404)

    signatories = LeaveSignatories.objects.filter(
        leave_id=leave.id
    ).select_related('emp__pi__user').order_by('signatory_type')

    # Load signature images + cert CN for all signatories
    for s in signatories:
        s.esignature = None
        s.cert_name = None  
        s.has_p12 = False  # Add this line

        if s.status == 1:  # only approved signatures
            try:
                sig_record = Signature.objects.filter(emp_id=s.emp.id).first()
                if sig_record:
                    # ✅ check kung naa bay p12
                    if sig_record.p12_file and sig_record.p12_password_enc:
                        s.has_p12 = True   

                    # ✅ signature image
                    if sig_record.signature_img:
                        with open(sig_record.signature_img.path, 'rb') as f:
                            s.esignature = base64.b64encode(f.read()).decode('utf-8')

                    # ✅ extract cert CN direct from .p12
                    if sig_record.p12_file and sig_record.p12_password_enc:
                        with open(sig_record.p12_file.path, 'rb') as cert_file:
                            p12_data = cert_file.read()
                            try:
                                private_key, cert, add_certs = pkcs12.load_key_and_certificates(
                                    p12_data,
                                    decrypt_text(sig_record.p12_password_enc).encode()
                                )
                                if cert:
                                    for attr in cert.subject:
                                        if attr.oid == x509.oid.NameOID.COMMON_NAME:
                                            s.cert_name = attr.value
                                            break
                            except Exception as e:
                                print(f"Error parsing cert for emp {s.emp.id}: {e}")

            except Exception as e:
                print(f"Error loading signature for emp {s.emp.id}: {e}")

    has_p12 = any(s.has_p12 for s in signatories if s.status == 1)

    applicant_signatory = signatories.filter(signatory_type=0).first()
    section_head_signatory = signatories.filter(signatory_type=1).first()
    division_chief_signatory = signatories.filter(signatory_type=2).first()
    final_approval_signatory = signatories.filter(signatory_type=3).first()
    hr_approval_signatory = signatories.filter(signatory_type=4).first()

    if leave.leavesubtype_id == 12:
        designation = Designation.objects.filter(emp_id=leave.emp_id, id=1).first()
    else:
        designation = Designation.objects.filter(emp_id=leave.emp_id).first()

    if designation:
        first_level = PortalConfiguration.objects.filter(id=5).first()
        first_level_pos = first_level.key_name
        second_level = PortalConfiguration.objects.filter(id=6).first()
        second_level_pos = second_level.key_name
        classes = 3
    else:
        head = Designation.objects.filter(emp_id=leave.emp_id).first()
        div_head = Division.objects.filter(div_chief_id=leave.emp_id).first()
        sec_head = Section.objects.filter(sec_head_id=leave.emp_id).first()

        if div_head:
            if div_head.designation_id == 1 or head:
                first_level = ""
                first_level_pos = ""
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            else:
                first_level = div_head.designation.emp_id
                first_level_pos = Designation.objects.filter(
                    emp_id=div_head.designation.emp_id
                ).first()
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            classes = 2
        elif sec_head:
            if sec_head.div.designation_id == 1:
                first_level = None
                first_level_pos = ""
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            else:
                first_level = sec_head.div.div_chief_id 
                first_level_pos = Division.objects.filter(
                div_chief_id=sec_head.div.div_chief_id
            ).first()

                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            classes = 2

        else:
            emp = Empprofile.objects.filter(id=leave.emp_id).first()
            first_level = emp.section.div.div_chief_id
            first_level_pos = Division.objects.filter(
                div_chief_id=emp.section.div.div_chief_id
            ).first()

            if emp.aoa.name != "Field Office Caraga":
                second_level = emp.section.div.designation.emp_id
                second_level_pos = Designation.objects.filter(emp_id=second_level).first()
            else:
                fo_staff = PortalConfiguration.objects.filter(
                    key_name='Leave Second Level Signatory'
                ).first()
                second_level = fo_staff.key_acronym if fo_staff and fo_staff.key_acronym else None
                check = Designation.objects.filter(emp_id=second_level)
                second_level_pos = check if check else None
            classes = 1

    designations = Designation.objects.all()
    
    if division_chief_signatory:
        division_chief_signatory.designation_name = get_signatory_designation(division_chief_signatory)

        
    if final_approval_signatory:
        final_approval_signatory.designation_name = get_signatory_designation(final_approval_signatory)

    if hr_approval_signatory:
        hr_approval_signatory.designation_name = get_signatory_designation(hr_approval_signatory)

    signatory = None
    if hasattr(request.user, 'empprofile'):
        signatory = LeaveSignatories.objects.filter(
            leave_id=leave.id,
            emp_id=request.user.empprofile.id
        ).first()
    elif request.session.get('emp_id'):
        signatory = LeaveSignatories.objects.filter(
            leave_id=leave.id,
            emp_id=request.session.get('emp_id')
        ).first()

    context = {
        'leave': LeavespentApplication.objects.filter(
            leaveapp_id=pk, leaveapp__emp_id=leave.emp_id
        ).first(),
        'leavesubtype': LeaveSubtype.objects.filter(status=1).order_by('order'),
        'first_level': first_level,
        'first_level_pos': first_level_pos,
        'designations': designations,
        'second_level': second_level,
        'second_level_pos': second_level_pos,
        'classes': classes,
        'personnel_officer': PortalConfiguration.objects.filter(
            key_name='Personnel Officer'
        ).first(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'signatory': signatory,  
        'signatories': signatories, 
        'applicant_signatory': applicant_signatory,
        'section_head_signatory': section_head_signatory,
        'division_chief_signatory': division_chief_signatory,
        'final_approval_signatory': final_approval_signatory,
        'hr_approval_signatory': hr_approval_signatory,
        'has_p12': has_p12,  
    }

    return render(request, 'frontend/leave/print_leave_revised_2025.html', context)


@login_required
@permission_required('auth.leave')
def disapproved_leave_signatories(request):
    if request.method == "POST":
        id = request.POST.get('id')
        LeaveSignatories.objects.filter(id=id).update(status=2)
        return JsonResponse({'success': True})
    

def get_signatory_designation(signatory):
    if signatory and signatory.emp:
        if signatory.emp.designation:
            return signatory.emp.designation.upper()
    return ""
    
        

@login_required
def get_leave_totals(request):
    emp_id = request.session['emp_id']
    base = LeaveSignatories.objects.filter(
        emp_id=emp_id,
        status=0
    )

    prev_approved = LeaveSignatories.objects.filter(
        leave_id=OuterRef('leave_id'),
        signatory_type=ExpressionWrapper(OuterRef('signatory_type') - 1, output_field=IntegerField()),
        status=1
    )


    total_leave_application = LeaveApplication.objects.filter(
        emp_id=emp_id,
        status__in=[0, 1, 2]
    ).count()
    
    for_approval_count = base.annotate(prev_ok=Exists(prev_approved)) \
                             .filter(Q(signatory_type=0) | Q(signatory_type__gt=0, prev_ok=True)) \
                             .count()

    return JsonResponse({
        'for_approval': for_approval_count,
        'total_leave_application': total_leave_application
    })


def link_callback(uri, rel):
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    elif uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    else:
        return uri

    if not os.path.isfile(path):
        raise Exception(f"Static file not found: {uri}")
    return path



def set_signature_leave(request):
    if request.POST.get('recommended_by'):
        recommended_by = re.split(r'\[|\]', request.POST.get('recommended_by'))
        if len(recommended_by) > 1 and recommended_by[1]: 
            recommended_by_name = Empprofile.objects.filter(id_number=recommended_by[1]).first()
        else:
            recommended_by_name = None

        if recommended_by_name:
            check_recommended_by_position = Designation.objects.filter(emp_id=recommended_by_name.id).first()
            if check_recommended_by_position:
                recommended_by_position = check_recommended_by_position.name
            else:
                division = Division.objects.filter(div_chief_id=recommended_by_name.id).first()
                if division:
                    recommended_by_position = f"Chief, {division.div_acronym}"
                else:
                    section = Section.objects.filter(sec_head_id=recommended_by_name.id).first()
                    if section:
                        recommended_by_position = f"Head, {section.sec_acronym}"
                    else:
                        recommended_by_position = recommended_by_name.position.name

            first_level = recommended_by_name.pi.user.get_fullname.upper()
            first_level_pos = recommended_by_position
        else:
            first_level = None
            first_level_pos = None
             
    else:
        first_level = None
        first_level_pos = None

    if request.POST.get('approved_by'):
        approved_by_str = request.POST.get('approved_by')
        approved_by_data = approved_by_str.split('|')  
        approved_by_emp_id = approved_by_data[0] if len(approved_by_data) > 0 else None
        approved_by_id_number = approved_by_data[1] if len(approved_by_data) > 1 else None

        approved_by_name = Empprofile.objects.filter(id_number=approved_by_id_number).first() if approved_by_id_number else None

        if approved_by_name:
            check_approved_by_position = Designation.objects.filter(emp_id=approved_by_emp_id).first()
            if check_approved_by_position:
                approved_by_position = check_approved_by_position.name
                approved_by_position_wacronym = ''
            else:
                division = Division.objects.filter(div_chief_id=approved_by_name.id).first()
                if division:
                    approved_by_position = f"Chief, {division.div_acronym}"
                    approved_by_position_wacronym = f"Chief, {division.div_name}"
                else:
                    section = Section.objects.filter(sec_head_id=approved_by_name.id).first()
                    if section:
                        approved_by_position = f"Head, {section.sec_acronym}"
                        approved_by_position_wacronym = f"Head, {section.sec_name}"
                    else:
                        approved_by_position = approved_by_name.position.name

            second_level = approved_by_name.pi.user.get_fullname.upper()
            second_level_w_pos = f"{second_level}, {approved_by_position}"
            second_level_pos_not_acronym = approved_by_position_wacronym
            second_level_pos = approved_by_position
        else:
            second_level = None
            second_level_pos = None
            second_level_w_pos = None
            second_level_pos_not_acronym = None
    else:
        second_level = None
        second_level_pos = None
        second_level_w_pos = None
        second_level_pos_not_acronym = None
        
        
    context = {
         'first_level': first_level,
        'first_level_pos': first_level_pos,
        'second_level': second_level,
        'second_level_pos': second_level_pos,
        'second_level_w_pos': second_level_w_pos,
        'second_level_pos_not_acronym': second_level_pos_not_acronym
    }

    return JsonResponse({ context })



@login_required
def leave_after_print(request):
    if request.method == "POST":
        pk = request.POST.get('pk')
        if pk:
            try:
                leave = LeaveApplication.objects.get(id=pk)
                return JsonResponse({'success': True})
            except LeaveApplication.DoesNotExist:
                return JsonResponse({'error': 'Leave application not found'}, status=404)
    return JsonResponse({'error': 'Invalid request'}, status=400)
    
    


def convert_to_standard(days, hours, minutes):
    # calculate total minutes
    total_minutes = days*8*60 + hours*60 + minutes
    # calculate days, hours and minutes
    standard_days = total_minutes // (8*60)
    standard_hours = (total_minutes % (8*60)) // 60
    standard_minutes = total_minutes % 60
    # return as list
    return [standard_days, standard_hours, standard_minutes]


@login_required
def ctdo_requests(request):
    if request.method == "POST":
        with transaction.atomic():
            lasttrack = CTDORequests.objects.order_by('-id').first()
            track_num = generate_serial_string(lasttrack.tracking_no) if lasttrack else \
                generate_serial_string(None, 'CTDO')

            random_dates = request.POST.getlist('dates[]')
            type = request.POST.getlist('type[]')

            utilization = CTDOUtilization.objects.filter(emp_id=request.session['emp_id'], status=0)

            if utilization:
                ctdo = CTDORequests(
                    tracking_no=track_num,
                    start_date=request.POST.get('start_date') if request.POST.get('start_date') else None,
                    end_date=request.POST.get('end_date') if request.POST.get('end_date') else None,
                    date_filed=datetime.now(),
                    emp_id=request.session['emp_id'],
                    status=0,
                    remarks=request.POST.get('remarks')
                )

                # Save points for requesting a CTDO
                gamify(12, request.session['emp_id'])

                ctdo.save()

                total = convert_to_standard(int(request.POST.get('total_days')),
                                            int(request.POST.get('total_hours')),
                                            int(request.POST.get('total_minutes')))
                total_u = convert_to_standard(int(request.POST.get('total_u_days')),
                                              int(request.POST.get('total_u_hours')),
                                            int(request.POST.get('total_u_minutes')))

                CTDOHistoryBalance.objects.create(
                    total_days=total[0],
                    total_hours=total[1],
                    total_minutes=total[2],
                    total_u_days=total_u[0],
                    total_u_hours=total_u[1],
                    total_u_minutes=total_u[2],
                    ctdoreq_id=ctdo.id
                )

                utilization.update(
                    ctdoreq_id=ctdo.id,
                    status=1
                )

                CTDOCoc.objects.filter(emp_id=request.session['emp_id'], ctdoreq_id=None).update(
                    ctdoreq_id=ctdo.id
                )

                data = [{'dates': dates, 'type': type}
                        for dates, type in
                        zip(random_dates, type)]

                for row in data:
                    CTDORandomDates.objects.create(
                        ctdo_id=ctdo.id,
                        date=row['dates'],
                        type=row['type']
                    )

                return JsonResponse({'data': 'success', 'msg': 'This will serve as your tracking no. {}. Please wait for the reviewal of your ctdo request. Thank you.'.format(track_num)})
            else:
                return JsonResponse({'error': True, 'msg': 'The filing process for your CTDO cannot proceed without selecting your earned CoC. Please ensure to choose your earned CoC.'})
        return JsonResponse({'error': True, 'msg': 'System encountered an error. Please try again.'})

    coc = CTDOActualBalance.objects.filter(cocbal__emp_id=request.session['emp_id'], cocbal__status=1)

    list_days = []
    list_hours = []
    list_minutes = []
    for row in coc:
        if int(row.days) == 0 and int(row.hours) == 0 and int(row.minutes) == 0:
            CTDOBalance.objects.filter(id=row.cocbal_id).update(
                status=0
            )

        list_days.append(int(row.days))
        list_hours.append(int(row.hours))
        list_minutes.append(int(row.minutes))

    minutes = sum(list_minutes) // 60
    total_minutes = sum(list_minutes) - minutes * 60
    hours = sum(list_hours) // 8
    total_hours = (sum(list_hours) - hours * 8) + minutes
    total_days = sum(list_days) + hours
    standard = convert_to_standard(total_days, total_hours, total_minutes)

    context = {
        'date': datetime.now(),
        'tab_title': 'CTDO Requests (COS / JO)',
        'title': 'personnel_transactions',
        'sub_title': 'ctdo_request',
        'total_days': standard[0]
    }
    return render(request, 'frontend/leave/ctdo_requests.html', context)


@login_required
def coc_earned_content(request):
    CTDOBalance.objects.filter(date_expiry__lt=date.today()).update(
        status=2
    )

    coc = CTDOActualBalance.objects.filter(cocbal__emp_id=request.session['emp_id'], cocbal__status=1)

    list_days = []
    list_hours = []
    list_minutes = []
    for row in coc:
        if int(row.days) == 0 and int(row.hours) == 0 and int(row.minutes) == 0:
            CTDOBalance.objects.filter(id=row.cocbal_id).update(
                status=0
            )

        list_days.append(int(row.days))
        list_hours.append(int(row.hours))
        list_minutes.append(int(row.minutes))

    minutes = sum(list_minutes) // 60
    total_minutes = sum(list_minutes) - minutes * 60
    hours = sum(list_hours) // 8
    total_hours = (sum(list_hours) - hours * 8) + minutes
    total_days = sum(list_days) + hours

    utilization = CTDOUtilization.objects.filter(emp_id=request.session['emp_id'], status=0)

    list_u_days = []
    list_u_hours = []
    list_u_minutes = []
    for row in utilization:
        list_u_days.append(int(row.days))
        list_u_hours.append(int(row.hours))
        list_u_minutes.append(int(row.minutes))

    u_minutes = sum(list_u_minutes) // 60
    total_u_minutes = sum(list_u_minutes) - u_minutes * 60
    u_hours = sum(list_u_hours) // 8
    total_u_hours = (sum(list_u_hours) - u_hours * 8) + u_minutes
    total_u_days = sum(list_u_days) + u_hours

    standard_u = convert_to_standard(total_u_days, total_u_hours, total_u_minutes)
    now = timezone.now()
    total_utilization = CTDORandomDates.objects.filter(ctdo__date_filed__year=now.year,
                                                       ctdo__date_filed__month=now.month,
                                                       ctdo__emp_id=request.session['emp_id'],
                                                       ctdo__status__in=[0, 1])

    for row in coc:
        check = CTDOCoc.objects.filter(emp_id=request.session['emp_id'], ctdoreq_id=None, month_earned=row.cocbal.month_earned)
        if not check:
            CTDOCoc.objects.create(
                month_earned=row.cocbal.month_earned,
                days=row.days,
                hours=row.hours,
                minutes=row.minutes,
                expiry_date=row.cocbal.date_expiry,
                emp_id=request.session['emp_id']
            )

    context = {
        'coc': CTDOActualBalance.objects.filter(cocbal__emp_id=request.session['emp_id'], cocbal__status=1),
        'total_days': total_days,
        'total_hours': total_hours,
        'total_minutes': total_minutes,
        'utilization': utilization,
        'total_u_days': standard_u[0],
        'total_u_hours': standard_u[1],
        'total_u_minutes': standard_u[2],
        'total_utilization': total_utilization.count()
    }
    return render(request, 'frontend/leave/coc_earned_content.html', context)


@login_required
@csrf_exempt
def delete_coc_utilization(request):
    if request.POST.get('ctdoreq_id'):
        utilization = CTDOUtilization.objects.filter(ctdoreq_id=request.POST.get('ctdoreq_id'), emp_id=request.POST.get('token'))
    else:
        utilization = CTDOUtilization.objects.filter(ctdoreq_id=None, emp_id=request.POST.get('token'))

    coc_actual_balance = CTDOActualBalance.objects.filter(id=utilization.first().cocactualbal_id)
    CTDOBalance.objects.filter(id=coc_actual_balance.first().cocbal_id).update(
        status=1
    )

    coc_actual_balance.update(
        days=F('days') + int(utilization.first().days),
        hours=F('hours') + int(utilization.first().hours),
        minutes=F('minutes') + int(utilization.first().minutes),
    )

    standard_format = convert_to_standard(int(coc_actual_balance.first().days),
                        int(coc_actual_balance.first().hours),
                        int(coc_actual_balance.first().minutes))

    coc_actual_balance.update(
        days=standard_format[0],
        hours=standard_format[1],
        minutes=standard_format[2],
    )

    utilization.delete()
    return JsonResponse({'data': 'success', 'msg': 'Your earned CoC for utilization has been removed successfully.'})


class Balance:
    def __init__(self, id, days, hours, minutes):
        self.id = id
        self.days = days
        self.hours = hours
        self.minutes = minutes

    def to_minutes(self):
        return self.days * 8 * 60 + self.hours * 60 + self.minutes

    def subtract(self, other):
        new_minutes = max(self.to_minutes() - other.to_minutes(), 0)
        days, hours, minutes = convert_to_standard(0, 0, new_minutes)
        return Balance(self.id, days, hours, minutes)


def get_first_date(obj):
    dates = obj.cocbal.month_earned.split(',')
    first_date_str = f'{dates[0].strip()}, {dates[-1].strip()}'
    return parse(first_date_str)


@login_required
@csrf_exempt
def auto_utilize_coc_earned(request):
    if request.method == "POST":
        days = int(request.POST.get('days'))
        hours = int(request.POST.get('hours'))
        if days != 0 or hours !=0:
            actual_balance = (CTDOActualBalance.objects
                              .filter(cocbal__emp_id=request.session['emp_id'], cocbal__status=1)
                              .annotate(total_time=F('days') * 8 * 60 + F('hours') * 60 + F('minutes')))

            actual_balance = list(actual_balance)
            actual_balance.sort(key=get_first_date)

            utilized = []
            remaining = []

            input_days_hours = Balance(None, days, hours, 0)

            for row in actual_balance:
                current_balance = Balance(row.id, int(row.days), int(row.hours), int(row.minutes))

                if current_balance.to_minutes() > input_days_hours.to_minutes():
                    utilized_amount = input_days_hours.to_minutes()
                    new_balance = current_balance.subtract(input_days_hours)
                else:
                    utilized_amount = current_balance.to_minutes()
                    new_balance = Balance(row.id, 0, 0, 0)

                if utilized_amount > 0:
                    days, hours, minutes = convert_to_standard(0, 0, utilized_amount)
                    utilized.append(Balance(row.id, days, hours, minutes))
                    remaining.append(new_balance)
                    days, hours, minutes = convert_to_standard(0, 0, input_days_hours.to_minutes() - utilized_amount)
                    input_days_hours = Balance(None, days, hours, minutes)

            for balance in remaining:
                CTDOActualBalance.objects.filter(id=balance.id).update(
                    days=balance.days,
                    hours=balance.hours,
                    minutes=balance.minutes
                )

            for balance in utilized:
                CTDOUtilization.objects.create(
                    cocactualbal_id=balance.id,
                    days=balance.days,
                    hours=balance.hours,
                    minutes=balance.minutes,
                    emp_id=request.session['emp_id'],
                    status=0
                )

            return JsonResponse({'data': 'success', 'msg': 'Auto utilization completed. You can now select a dates for your ctdo application.'})
        else:
            return JsonResponse({'error': True, 'msg': 'Processing is not possible due to insufficient balance for utilization.'})


@login_required
@csrf_exempt
def request_for_ctdo_cancellation(request):
    if request.method == "POST":
        CTDORequests.objects.filter(id=request.POST.get('id')).update(
            status=3
        )

        return JsonResponse({'data': 'success', 'msg': 'You have successfully request for cancellation on your CTDO Application.'})


@login_required
def utilize_coc_earned(request, pk):
    id = force_token_decryption(pk)
    coc = CTDOActualBalance.objects.filter(id=id).first()
    if request.method == "POST":
        if int(request.POST.get('days')) <= int(coc.days) and int(request.POST.get('hours')) <= int(coc.hours) and int(request.POST.get('days')) <= int(coc.minutes):
            CTDOActualBalance.objects.filter(id=id).update(
                days=F('days') - int(request.POST.get('days')),
                hours=F('hours') - int(request.POST.get('hours')),
                minutes=F('minutes') - int(request.POST.get('minutes')),
            )

            CTDOUtilization.objects.create(
                days=request.POST.get('days'),
                hours=request.POST.get('hours'),
                minutes=request.POST.get('minutes'),
                cocactualbal_id=coc.id,
                emp_id=coc.cocbal.emp_id,
                status=0
            )

            return JsonResponse({'data': 'success', 'msg': 'Successfully added! Your earned CoC is now available for your utilization.'})
        else:
            return JsonResponse({'error': True, 'msg': 'Insufficient balance. Please refer to personnel administration section to file your coc earned.'})

    context = {
        'coc': coc,
        'pk': pk
    }
    return render(request, 'frontend/leave/utilize_coc.html', context)


def convert_to_minutes(days, hours, minutes):
    return days*8*60 + hours*60 + minutes


def convert_to_days_hours_minutes(minutes):
    days = minutes // (8*60)
    minutes %= 8*60
    hours = minutes // 60
    minutes %= 60
    return days, hours, minutes


@login_required
def print_ctdo(request, pk):
    data = CTDORequests.objects.filter(id=pk).first()
    emp = Empprofile.objects.filter(id=data.emp_id).first()

    if emp.section.div.div_name == "Office of the Regional Director":
        first_level = emp.section.sec_head_id
    else:
        first_level = emp.section.div.div_chief_id

    designation = Designation.objects.filter(id=1).first()
    second_level = designation.emp_id
    second_level_pos = designation.name

    history = CTDOHistoryBalance.objects.filter(ctdoreq_id=pk).first()

    available = [history.total_days if history is not None else 0,
                 history.total_hours if history is not None else 0,
                 history.total_minutes if history is not None else 0]
    applied = [history.total_u_days if history is not None else 0,
               history.total_u_hours if history is not None else 0,
               history.total_u_minutes if history is not None else 0]

    available_minutes = convert_to_minutes(*available)
    applied_minutes = convert_to_minutes(*applied)

    balance = [0, 0, 0]

    # Only calculate the remaining balance if the available minutes exceed the applied minutes
    if available_minutes >= applied_minutes:
        balance_minutes = available_minutes - applied_minutes
        balance = list(convert_to_days_hours_minutes(balance_minutes))

        if balance[1] < 0:  # if hours are negative
            balance[0] -= 1
            balance[1] += 8

        if balance[2] < 0:  # if minutes are negative
            balance[1] -= 1
            balance[2] += 60

        if balance[1] < 0:  # if hours are still negative
            balance[0] -= 1
            balance[1] += 8
    if emp.empstatus.id in [1, 2]:
        context = {
            'data': data,
            'history': history,
            'total_b_days': balance[0] if history else None,
            'total_b_hours': balance[1] if history else None,
            'total_b_minutes': balance[2] if history else None,
            'personnel_officer': PortalConfiguration.objects.filter(key_name='Personnel Officer').first(),
            'first_level': first_level,
            'second_level': second_level,
            'second_level_pos': second_level_pos
        }
        return render(request, 'frontend/leave/print_ctdo.html', context)
    else:
        head = Designation.objects.filter(emp_id=emp.id).first()
        div_head = Division.objects.filter(div_chief_id=emp.id).first()
        sec_head = Section.objects.filter(sec_head_id=emp.id).first()

        if div_head:
            if div_head.designation_id == 1 or head:  # PPD
                first_level = ""
                first_level_pos = ""
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            else:
                first_level = div_head.designation.emp_id
                first_level_pos = Designation.objects.filter(emp_id=div_head.designation.emp_id).first()
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            classes = 2
        elif sec_head:
            if sec_head.div.designation_id == 1:  # PPD
                first_level = ""
                first_level_pos = ""
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            else:
                first_level = sec_head.div.designation.emp_id
                first_level_pos = Designation.objects.filter(emp_id=sec_head.div.designation.emp_id).first()
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            classes = 2
        else:
            emp = Empprofile.objects.filter(id=emp.id).first()
            first_level = emp.section.div.div_chief_id
            first_level_pos = Division.objects.filter(div_chief_id=emp.section.div.div_chief_id).first()

            if emp.aoa.name != "Field Office Caraga":
                second_level = emp.section.div.designation.emp_id
                second_level_pos = Designation.objects.filter(emp_id=emp.section.div.designation.emp_id).first()
            else:
                fo_staff = PortalConfiguration.objects.filter(key_name='Leave Second Level Signatory').first()
                second_level = fo_staff.key_acronym if fo_staff.key_acronym else None
                check = Designation.objects.filter(emp_id=fo_staff.key_acronym)
                if check:
                    second_level_pos = check
                else:
                    second_level_pos = None
            classes = 1

        context = {
            'data': data,
            'first_level': first_level,
            'first_level_pos': first_level_pos,
            'second_level': second_level,
            'second_level_pos': second_level_pos,
            'classes': classes,
            'leavesubtype': LeaveSubtype.objects.order_by('order'),
            'personnel_officer': PortalConfiguration.objects.filter(key_name='Personnel Officer').first(),
            'history': history,
        }
        return render(request, 'frontend/leave/print_regcon_ctdo.html', context)


@login_required
@csrf_exempt
def ctdo_add_remarks(request):
    if request.method == "POST":
        CTDORequests.objects.filter(id=request.POST.get('pk')).update(
            remarks=request.POST.get('remarks')
        )

        return JsonResponse({'data': 'success'})


@login_required
@csrf_exempt
def cancel_ctdo(request):
    if request.method == "POST":
        with transaction.atomic():
            ctdo = CTDORequests.objects.filter(id=request.POST.get('id'))
            ctdo.update(
                status=2
            )

            utilization = CTDOUtilization.objects.filter(ctdoreq_id=request.POST.get('id'))
            if utilization:
                for row in utilization:
                    CTDOBalance.objects.filter(id=row.cocactualbal.cocbal_id).update(
                        status=1
                    )

                    CTDOActualBalance.objects.filter(id=row.cocactualbal_id).update(
                        days=F('days') + int(row.days),
                        hours=F('hours') + int(row.hours),
                        minutes=F('minutes') + int(row.minutes),
                    )

            message = "Good day, {}! Your CTDO request with tracking number {} has been cancelled by the administrator. - The My PORTAL Team".format(
                ctdo.first().emp.pi.user.first_name,
                ctdo.first().tracking_no)
            if ctdo.first().emp.pi.mobile_no:
                t = threading.Thread(target=send_notification,
                                     args=(message, ctdo.first().emp.pi.mobile_no, request.session['emp_id'], ctdo.first().emp.id))
                t.start()

            return JsonResponse({'data': 'success', 'msg': "The cancellation of CTDO with the tracking number {} has been successfully processed.".format(ctdo.first().tracking_no)})
        return JsonResponse({'error': True, 'msg': 'System encountered an error. Please try again later.'})


@login_required
@csrf_exempt
def ctdo_after_print(request):
    if request.method == "POST":
        CTDOPrintLogs.objects.create(
            ctdo_id=request.POST.get('pk')
        )

        return JsonResponse({'data': 'success' })
    
    
@login_required
def set_signatories_for_leave(request, pk, type=1):
    if request.method == "POST":
        approved = LeaveSignatories.objects.filter(leave_id=pk,status=1 ).exists()

        if approved:
            return JsonResponse({ 'success': False, 'message': ( 'This leave request is already being processed. Please contact the next approver if you wish to cancel.' )})

        requested_by = request.POST.get('requested_by')
        noted_by = request.POST.get('noted_by')
        approved_by = request.POST.get('approved_by')
        section_head = request.POST.get('section_head_approval')
        hr_approval = request.POST.get('hr_approval')

        def get_emp_id(val):
            parts = re.split(r'\[|\]', val) if val else []
            return parts[1] if len(parts) > 1 else None

        req_emp_id = get_emp_id(requested_by)
        noted_emp_id = get_emp_id(noted_by)
        approve_emp_id = get_emp_id(approved_by)
        section_head_emp_id = get_emp_id(section_head)
        hr_emp_id = get_emp_id(hr_approval)

        emp_request = Empprofile.objects.filter(id_number=req_emp_id).first()
        emp_noted_by = Empprofile.objects.filter(id_number=noted_emp_id).first()
        emp_approve_by = Empprofile.objects.filter(id_number=approve_emp_id).first()
        emp_hr = Empprofile.objects.filter(id_number=hr_emp_id).first()
        emp_sec_head = Empprofile.objects.filter(id_number=section_head_emp_id).first() if section_head_emp_id else None

        emp = Empprofile.objects.filter(id=request.session['emp_id']).first()
        sec_head = Section.objects.filter(id=emp.section_id).first()
        div_head = Division.objects.filter(id=sec_head.div_id).first() if sec_head else None

        req_sec_head = emp_request and sec_head and emp_request.id == sec_head.sec_head_id
        req_div = emp_request and div_head and emp_request.id == div_head.div_chief_id

        def upsert(signatory_type, emp_obj):
            if emp_obj:
                qs = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=signatory_type)
                if qs.exists():
                    qs.update(emp_id=emp_obj.id)
                else:
                    LeaveSignatories.objects.create(leave_id=pk,emp_id=emp_obj.id, signatory_type=signatory_type,status=0)

        upsert(0, emp_request)

        # Section Head 
        if not req_sec_head and not req_div and emp_sec_head:
            upsert(1, emp_sec_head)

        # Division Chief 
        if not req_div and emp_noted_by:
            upsert(2, emp_noted_by)

        # Approving Authority 
        if emp_approve_by:
            upsert(3, emp_approve_by)

        # HR
        if emp_hr:
            upsert(4, emp_hr)

        return JsonResponse({'success': True})

    emp = Empprofile.objects.filter(id=request.session['emp_id']).first()
    section_head = Section.objects.filter(id=emp.section_id).first() if emp else None
    division_head = Division.objects.filter(id=section_head.div_id).first() if section_head else None
    hr_pas_head_section = Section.objects.filter(sec_name='Personnel Administration').first()
    hr_pas_head_emp = Empprofile.objects.filter(id=hr_pas_head_section.sec_head_id).first() if hr_pas_head_section else None

    designation = Designation.objects.filter(name='Regional Director').first()
    requested_by = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=0).first()
    section_head_approval = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=1).first()
    noted_by = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=2).first()
    approved_by = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=3).first()
    hr_approval = LeaveSignatories.objects.filter(leave_id=pk, signatory_type=4).first()

    requested_by_record = LeaveSignatories.objects.filter(
        leave_id=pk, signatory_type=0
    ).select_related('emp').first()
    requester_emp = requested_by_record.emp if requested_by_record else emp

    hide_section_head = (
        (section_head and requester_emp.id == section_head.sec_head_id) or
        (division_head and emp.id == division_head.div_chief_id)
    )

    hide_div_chief = division_head and requester_emp.id == division_head.div_chief_id

    context = {
        'signatories': LeaveSignatories.objects.filter(leave_id=pk).order_by('signatory_type'),
        'section_head': section_head,
        'division_head': division_head,
        'hr_pas_head_emp': hr_pas_head_emp,
        'hr_approval': hr_approval,
        'hr_pas_head_section': hr_pas_head_section,
        'designation': designation,
        'requested_by': requested_by,
        'noted_by': noted_by,
        'approved_by': approved_by,
        'section_head_approval': section_head_approval,
        'type': type,
        'hide_section_head': hide_section_head,
        'hide_div_chief': hide_div_chief,
    }

    return render(request, 'frontend/leave/modals/set_signatories_content.html', context)


@login_required
def download_signed_leaveapp_multi(request, pk):
    leave = LeaveApplication.objects.filter(pk=pk).first()
    if not leave:
        return HttpResponse("Leave application not found.", status=404)

    emp_id = None
    if hasattr(request.user, 'empprofile'):
        emp_id = request.user.empprofile.id
    elif request.session.get('emp_id'):
        emp_id = request.session.get('emp_id')

    if not emp_id:
        return HttpResponse("Unable to identify current user.", status=400)

    is_applicant = leave.emp_id == emp_id
    is_signatory = LeaveSignatories.objects.filter(leave_id=leave.id, emp_id=emp_id).exists()
    
    if not (is_applicant or is_signatory):
        return HttpResponse("You are not authorized to download this document.", status=403)

    current_user_password = request.session.get('p12_password')
    if not current_user_password:
        return HttpResponse("Missing digital certificate password.", status=400)

    try:
        context = get_leave_context_multi(pk, request)
        html_content = render_to_string(
            'frontend/leave/print_leave_revised_2025.html',
            context,
            request=request
        )

        from weasyprint import HTML
        pdf_buffer = io.BytesIO()
        HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf(
            target=pdf_buffer
        )

        approved_signatories = LeaveSignatories.objects.filter(
            leave_id=leave.id, 
            status=1,  
            date__isnull=False  
        ).select_related('emp').order_by('date') 

        if not approved_signatories.exists():
            pdf_buffer.seek(0)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="leave_application.pdf"'
            return response

        current_pdf_buffer = io.BytesIO(pdf_buffer.getvalue())
        signature_count = 0
        
        for index, signatory in enumerate(approved_signatories):
            signature_record = Signature.objects.filter(emp_id=signatory.emp.id).first()
            
            if signature_record and signature_record.p12_file:
                try:
                    # Get this signatory's individual password
                    signatory_password = get_signatory_password(signatory.emp.id, current_user_password)
                    
                    validation = validate_p12_certificate(signatory.emp.id, signatory_password)
                    if validation['valid']:
                        print(f"Applying signature {signature_count + 1} for {signatory.emp.pi.user.get_full_name()}")
                        
                        new_pdf_buffer = multiple_signatories(
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
        filename = f"signed_leave_application_{signature_count}_sigs.pdf"
        response = HttpResponse(current_pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in download_signed_leaveapp_multi: {str(e)}")
        return HttpResponse(f"Error generating signed PDF: {str(e)}", status=500)


@csrf_exempt  
@login_required
def sign_uploaded_pdf(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    uploaded_pdf = request.FILES.get('pdf_file')
    if not uploaded_pdf:
        return JsonResponse({'error': 'Missing PDF file'}, status=400)

    # Get current user's employee ID
    emp_id = None
    if hasattr(request.user, 'empprofile'):
        emp_id = request.user.empprofile.id
    elif request.session.get('emp_id'):
        emp_id = request.session.get('emp_id')
    else:
        return JsonResponse({'error': 'Unable to identify current user'}, status=400)

    current_user_signatory = LeaveSignatories.objects.filter(
        leave_id=pk, 
        emp_id=emp_id,
        status=1,  
        date__isnull=False  
    ).first()
    
    leave_app = LeaveApplication.objects.filter(pk=pk).first()
    is_applicant = leave_app and leave_app.emp_id == emp_id if leave_app else False
    
    if not current_user_signatory and not is_applicant:
        return JsonResponse({'error': 'You are not authorized to download this document'}, status=403)

    try:
        # Get all approved signatories for this leave application
        approved_signatories = LeaveSignatories.objects.filter(
            leave_id=pk, 
            status=1,  
            date__isnull=False  
        ).select_related('emp').order_by('date')  
        
        if not approved_signatories.exists():
            # If no approved signatures, just return the original PDF
            uploaded_pdf.seek(0)
            response = HttpResponse(uploaded_pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="leave_application.pdf"'
            return response

        current_pdf_buffer = io.BytesIO(uploaded_pdf.read())
        signature_count = 0
        
        # Apply signatures from all approved signatories
        for signatory in approved_signatories:
            sig_record = Signature.objects.filter(emp_id=signatory.emp.id).first()
            
            if sig_record and sig_record.p12_file:
                try:
                    # Get the signatory's stored password (decrypt from database)
                    signatory_password = None
                    if sig_record.p12_password_enc:
                        signatory_password = decrypt_text(sig_record.p12_password_enc)
                    else:
                        print(f"No stored password for signatory {signatory.emp.id}, skipping...")
                        continue
                    
                    # Validate the certificate with the stored password
                    validation = validate_p12_certificate(signatory.emp.id, signatory_password)
                    if not validation['valid']:
                        print(f"Invalid certificate for signatory {signatory.emp.id}: {validation['error']}")
                        continue
                    
                    # Apply the signature
                    current_pdf_buffer = multiple_signatories(
                        current_pdf_buffer,
                        sig_record,
                        signatory_password,
                        signatory,
                        signature_count
                    )
                    signature_count += 1
                    print(f"Applied signature {signature_count} for {signatory.emp.pi.user.get_full_name()}")
                    
                except Exception as e:
                    print(f"Could not apply signature for {signatory.emp.id}: {e}")
                    continue
            else:
                print(f"No P12 certificate found for signatory {signatory.emp.id}")

        current_pdf_buffer.seek(0)
        
        # Return the signed PDF
        filename = f"signed_leave_application_{signature_count}_signatures.pdf"
        response = HttpResponse(current_pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in sign_uploaded_pdf: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Signing failed: {str(e)}'}, status=500)





    
    

@csrf_exempt
def search_leave_tracking(request):
    tracking_no = request.GET.get("tracking_no")

    if not tracking_no:
        return JsonResponse({"error": "Tracking number is required"}, status=400)

    try:
        leave = LeaveApplication.objects.get(
            tracking_no=tracking_no,
            emp__pi__user_id=request.user.id
        )
    except LeaveApplication.DoesNotExist:   
        return JsonResponse({"error": "Tracking number not found"}, status=404)

    requester = leave.emp  
    req_role = "staff"
    if requester.section and requester.section.sec_head_id == requester.id:
        req_role = "section_head"
    elif requester.section and requester.section.div.div_chief_id == requester.id:
        req_role = "division_chief"

    if req_role == "staff":
        step_types = {
            0: "Requester",
            1: "Section Head",
            2: "Division Chief",
            3: "Approving Authority",
            4: "HR",
        }
    elif req_role == "section_head":
        step_types = {
            0: "Requester",
            1: "Division Chief",
            2: "Approving Authority",
            3: "HR",
        }
    elif req_role == "division_chief":
        step_types = {
            0: "Requester",
            1: "Approving Authority",
            2: "HR",
        }

    # Actual signatories from DB
    signatories = {
        sig.signatory_type: sig
        for sig in LeaveSignatories.objects.filter(leave=leave)
    }

    # Build steps dynamically
    steps = []
    for idx, (stype, label) in enumerate(step_types.items(), start=1):
        sig = signatories.get(stype)
        steps.append({
            "step": idx,
            "name": sig.emp.user.get_full_name() if sig and hasattr(sig.emp, "user") else (str(sig.emp) if sig else ""),
            "status": sig.status if sig else 0,
            "date": sig.date.strftime("%b %d, %Y %I:%M %p") if sig and sig.date else None,
            "signatory_type": stype,
            "label": label,
        })

    role = "other"
    emp_profile = getattr(request.user, "empprofile", None)
    if emp_profile:
        if emp_profile.section and emp_profile.section.sec_head_id == emp_profile.id:
            role = "section_head"
        elif emp_profile.section and emp_profile.section.div.div_chief_id == emp_profile.id:
            role = "division_chief"

    return JsonResponse({
        "tracking_no": leave.tracking_no,
        "leave_id": leave.id,
        "status": leave.get_status,
        "steps": steps,
        "user_role": role,
    })


#08-22-2025
@login_required
def get_tracking_numbers(request):
    search = request.GET.get("search", "")
    applications = []

    try:
        emp_profile = Empprofile.objects.get(pi__user=request.user.id)

        qs = LeaveApplication.objects.filter(
            emp_id=emp_profile.id,  
            tracking_no__icontains=search
        ).order_by('-date_of_filing')

        for app in qs:
            applications.append({
                "tracking_no": app.tracking_no,
                "inclusive": app.get_inclusive(),
                "status": app.get_status,
            })

    except Empprofile.DoesNotExist:
        pass

    return JsonResponse({"applications": applications})


@csrf_exempt
def upload_compensatory_request(request):
    if request.method == "POST":
        try:
            emp = get_object_or_404(Empprofile, id=request.session['emp_id'])

            file = request.FILES.get("attachment")
            if not file:
                return JsonResponse({"status": "error", "msg": "No file uploaded."}, status=400)

            leavecompen = LeaveCompenattachment.objects.create(
                file_attachement=file,
                requester=emp
            )

            return JsonResponse({
                "status": "success",
                "msg": "Your compensatory credit request has been submitted.",
                "file": leavecompen.file_attachement.url,
                "uploaded_at": leavecompen.uploaded_at.strftime("%Y-%m-%d %I:%M %p"),
                "tracking_number": leavecompen.compen_tracking
            })

        except Exception as e:
            return JsonResponse({"status": "error", "msg": f"Server error: {str(e)}"}, status=500)

    return JsonResponse({"status": "error", "msg": "Invalid request."}, status=400)



@csrf_exempt
def submit_compensatory_request(request):
    if request.method == "POST":
        try:
            compensatory_id = request.POST.get('id')
            
            compensatory = get_object_or_404(LeaveCompenattachment, id=compensatory_id)
            
            emp = get_object_or_404(Empprofile, id=request.session['emp_id'])
            if compensatory.requester != emp:
                return JsonResponse({"status": "error", "msg": "Unauthorized action."}, status=403)
            
            if compensatory.status != 0:
                return JsonResponse({"status": "error", "msg": "Request has already been processed."}, status=400)
            
            compensatory.status = 1
            compensatory.save()
            
            return JsonResponse({
                "status": "success", 
                "msg": "Compensatory request submitted successfully!"
            })
            
        except Exception as e:
            return JsonResponse({"status": "error", "msg": f"Server error: {str(e)}"}, status=500)
    
    return JsonResponse({"status": "error", "msg": "Invalid request method."}, status=400)



@login_required
@csrf_exempt
@permission_required('auth.leave')
def delete_compen(request):
    if request.method == "POST":
        LeaveCompenattachment.objects.filter(id=request.POST.get('id')).delete()
        return JsonResponse({'data': 'success'})
    
    
    
@login_required
@csrf_exempt
@permission_required('auth.leave')
def cancel_compen(request):
    
    if request.method == "POST":
        remarks = request.POST.get('remarks')
        
        LeaveCompenattachment.objects.filter(id=request.POST.get('id')).update(status=3,remarks=remarks)
        return JsonResponse({'data':'success'})
    


@login_required
@csrf_exempt
def ctdo_after_print(request):
    if request.method == "POST":
        CTDOPrintLogs.objects.create(
            ctdo_id=request.POST.get('pk')
        )

        return JsonResponse({'data': 'success' })