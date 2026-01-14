import base64
import os
import io
from django.conf import settings
from backend.libraries.leave.models import LeaveSubtype,LeavespentApplication
from backend.models import Section, Division, Designation, Empprofile
from frontend.models import PortalConfiguration
from backend.libraries.leave.models import LeaveSignatories,Signature
from datetime import datetime
from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec,append_signature_field
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.images import PdfImage
from pyhanko.stamp import StaticStampStyle
from pyhanko.sign.signers import  PdfSigner, PdfSignatureMetadata
from pyhanko.pdf_utils.images import PdfImage
from PIL import Image,ImageDraw,ImageFont
from cryptography.fernet import Fernet    



def get_leave_context_multi(pk, request):
  
    leave = LeavespentApplication.objects.filter( leaveapp_id=pk ).select_related('leaveapp__emp__pi__user', 'leaveapp__emp__section').first()
    
    if not leave:
        return {}

    signatories = LeaveSignatories.objects.filter(
        leave_id=leave.leaveapp.id
    ).select_related('emp__pi__user').order_by('signatory_type')

    for s in signatories:
        s.esignature = None
        s.validation_stamp_b64 = None
        
        if s.status == 1 and s.date is not None:
            try:
                sig_record = Signature.objects.filter(emp_id=s.emp.id).first()
                if sig_record and sig_record.signature_img:
                    with open(sig_record.signature_img.path, 'rb') as f:
                        s.esignature = base64.b64encode(f.read()).decode('utf-8')
                    
                    signed_date = s.date.strftime('%Y-%m-%d %H:%M')
                    cert_name = f"{s.emp.pi.user.first_name} {s.emp.pi.user.last_name}"
                    
                    s.validation_stamp_b64 = generate_validated_signature_stamp(
                        sig_record, 
                        signed_date, 
                        cert_name, 
                        s.signatory_type
                    )
                    
                    print(f"Loaded signature for approved signatory: {cert_name} (Type: {s.signatory_type})")
                    
            except Exception as e:
                print(f"Error loading signature for emp {s.emp.id}: {e}")
        else:
            print(f"Skipping non-approved signatory: {s.emp.pi.user.get_full_name()} (Status: {s.status})")

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
                first_level_pos = Designation.objects.filter(emp_id=div_head.designation.emp_id).first()
                second_level = Designation.objects.filter(id=1).first()
                second_level_pos = second_level.name
            classes = 2
        elif sec_head:
            if sec_head.div.designation_id == 1:
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
            emp = Empprofile.objects.filter(id=leave.emp_id).first()
            first_level = emp.section.div.div_chief_id
            first_level_pos = Division.objects.filter(div_chief_id=emp.section.div.div_chief_id).first()

            if emp.aoa.name != "Field Office Caraga":
                second_level = emp.section.div.designation.emp_id
                second_level_pos = Designation.objects.filter(emp_id=second_level).first()
            else:
                fo_staff = PortalConfiguration.objects.filter(key_name='Leave Second Level Signatory').first()
                second_level = fo_staff.key_acronym if fo_staff and fo_staff.key_acronym else None
                check = Designation.objects.filter(emp_id=second_level)
                second_level_pos = check if check else None
            classes = 1

    context = {
        'leave': leave,
        'leavesubtype': LeaveSubtype.objects.filter(status=1).order_by('order'),
        'first_level': first_level,
        'first_level_pos': first_level_pos,
        'designations': Designation.objects.all(),
        'second_level': second_level,
        'second_level_pos': second_level_pos,
        'classes': classes,
        'personnel_officer': PortalConfiguration.objects.filter(key_name='Personnel Officer').first(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'signatories': signatories,  
    }

    return context




def get_signatory_role_name(signatory_type):
    roles = {
        0: "Requester",
        1: "Section Head", 
        2: "Division Chief",
        3: "Approving Authority",
        4: "HR Officer"
    }
    return roles.get(signatory_type, "Signatory")


def get_signature_positions():


    return {
        
        0: (400, 390, 500, 445),    # Requester 
        1: (480, 200, 596, 255),    # Section 
        2: (416, 215, 516, 270),    # Division Chief 
        3: (250, 75, 360, 130),     # Approving Authority 
        4: (80, 205, 300, 265),     # HR Officer 
    }
    
def load_font_cross_platform(size, bold=False):
    """Cross-platform font loading that works on both Windows and Ubuntu"""
    import os
    import platform
    
    try:
        # Try Windows fonts first
        if bold:
            return ImageFont.truetype("arialbd.ttf", size=size)
        return ImageFont.truetype("arial.ttf", size=size)
    except:
        # Try Ubuntu/Linux fonts
        try:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf" if bold else "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size=size)
        except:
            pass
        
        # Final fallback
        return ImageFont.load_default()


def generate_signature_stamp(signature, signed_time, cert_full_name):
    if not signature.signature_img:
        return None

    output_path = f"media/signed_stamps/stamp_{signature.id}.png"
    if os.path.exists(output_path):
        with open(output_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    # Load the signature image
    img = Image.open(signature.signature_img.path).convert("RGBA").resize((120, 100))

    canvas_width = 280
    canvas_height = 100
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 0))  # transparent

    # Paste signature image
    canvas.paste(img, (0, 0), mask=img)

    draw = ImageDraw.Draw(canvas)
    font = load_font_cross_platform(16)  # Use the cross-platform function
        
    draw.text((130, 10), "Digitally signed by:", fill=(0, 0, 0), font=font)
    draw.text((130, 30), cert_full_name, fill=(0, 0, 0), font=font)
    draw.text((130, 50), signed_time, fill=(0, 0, 0), font=font)
    canvas.save(output_path, format='PNG')

    with open(output_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def generate_validated_signature_stamp(signature, signed_date, cert_name, signatory_type):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io, base64, os

        canvas_width = 600
        canvas_height = 320   
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 0))  
        draw = ImageDraw.Draw(canvas)

        def load_font(size, bold=False):
            return load_font_cross_platform(size, bold)  # Use the cross-platform function

        # Uniform font
        uniform_font_size = 50
        font_normal = load_font(uniform_font_size)
        font_bold = load_font(uniform_font_size, bold=True)

        if signature.signature_img and os.path.exists(signature.signature_img.path):
            try:
                sig_img = Image.open(signature.signature_img.path).convert("RGBA")
                sig_img = sig_img.resize((400, 200), Image.Resampling.LANCZOS)  
                sig_x = (canvas_width - sig_img.width) // 2 - 100   # center horizontally
                canvas.paste(sig_img, (sig_x, 5), mask=sig_img)
            except Exception as e:
                print(f"Error loading signature image: {e}")

        max_text_width = 420
        font_name = font_bold
        font_name_size = uniform_font_size
        while True:
            text_bbox = draw.textbbox((0, 0), cert_name, font=font_name)
            text_width = text_bbox[2] - text_bbox[0]
            if text_width <= max_text_width or font_name_size <= 16:
                break
            font_name_size -= 2
            font_name = load_font(font_name_size, bold=True)

        # text position
        text_x = 40
        y_offset = 150  # Start text under the signature
        line_spacing = 50  # gap of text

        draw.text((text_x, y_offset), "Digitally signed by", fill=(0, 0, 0), font=font_normal)
        draw.text((text_x, y_offset + line_spacing), cert_name, fill=(0, 0, 0), font=font_normal)
        draw.text((text_x, y_offset + line_spacing * 2), signed_date, fill=(80, 80, 80), font=font_normal)

        # Convert to base64
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return img_str

    except Exception as e:
        print(f"Error generating validated signature stamp: {e}")
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="




def get_multiple_position(signatory, leave_id):

    allSignatories = LeaveSignatories.objects.filter(leave_id=leave_id ).select_related('emp').order_by('signatory_type')
    
    requester = allSignatories.filter(signatory_type=0).first()
    if not requester:
        return 0  
    
    emp = Empprofile.objects.filter(id=requester.emp.id).first()
    if not emp:
        return signatory.signatory_type  
        
    sec_head = Section.objects.filter(id=emp.section_id).first()
    div_head = Division.objects.filter(id=sec_head.div_id).first() if sec_head else None
    
    req_is_sec_head = sec_head and requester.emp.id == sec_head.sec_head_id
    req_is_div_chief = div_head and requester.emp.id == div_head.div_chief_id
    
    
    if req_is_div_chief:
        if signatory.signatory_type == 0:  
            return 0  
        elif signatory.signatory_type == 3:  
            return 3  
        elif signatory.signatory_type == 4: 
            return 4  
            
    elif req_is_sec_head:
        if signatory.signatory_type == 0:  
            return 0 
        elif signatory.signatory_type == 2:  
            return 2  
        elif signatory.signatory_type == 3:  
            return 3  
        elif signatory.signatory_type == 4:  
            return 4  
        
    else:
        return signatory.signatory_type
    

    return signatory.signatory_type


def multiple_signatories(input_pdf_buffer, signature_record, password, signatory, signature_index):
    try:
        # Check if user has p12 certificate
        has_p12 = signature_record.p12_file and os.path.exists(signature_record.p12_file.path)
        
        if has_p12:
            # Use p12 certificate for signing
            try:
                signer = signers.SimpleSigner.load_pkcs12(
                    pfx_file=signature_record.p12_file.path,
                    passphrase=password.encode()
                )
            except Exception as e:
                print(f"Failed to load P12 certificate: {e}")
                return input_pdf_buffer

            try:
                cert_subject = signer.signing_cert.subject.native
                certname = cert_subject.get('common_name')

                if not certname:
                    certname = cert_subject.get('organization_name') or cert_subject.get('email_address')

                if not certname and hasattr(signature_record, 'emp') and hasattr(signature_record.emp, 'pi') and hasattr(signature_record.emp.pi, 'user'):
                    user = signature_record.emp.pi.user
                    certname = f"{user.first_name} {user.last_name}"

                if not certname:
                    certname = "Unknown Signer"

            except Exception as e:
                print(f"Error retrieving signer name: {e}")
                certname = "Unknown Signer"

            # Continue with p12-based signing process
            signeddate = signatory.date.strftime('%Y-%m-%d %H:%M') if signatory.date else datetime.now().strftime('%Y-%m-%d %H:%M')

            signature_base64 = generate_validated_signature_stamp(
                signature_record, signeddate, certname, signatory.signatory_type
            )
            signature_image = base64.b64decode(signature_base64)

            leave_id = signatory.leave_id if hasattr(signatory, 'leave_id') else None
            visual_position = get_multiple_position(signatory, leave_id)
            
            sig_positions = get_signature_positions()
            box = sig_positions.get(
                visual_position,  
                (50, 400 - (signature_index * 80), 300, 455 - (signature_index * 80))
            )

            input_pdf_buffer.seek(0)
            writer = IncrementalPdfFileWriter(input_pdf_buffer)
            output_pdf = io.BytesIO()

            timestamp = int(datetime.now().timestamp())
            field_name = f"Sig_{visual_position}_{signatory.emp.id}_{timestamp}"

            append_signature_field(
                writer,
                SigFieldSpec(sig_field_name=field_name, on_page=0, box=box)
            )

            pdf_signer = PdfSigner(
                signature_meta=PdfSignatureMetadata(
                    field_name=field_name,
                    name=certname,
                    location="Leave Management System",
                    reason=f"Leave Application Approval - {get_signatory_role_name(signatory.signatory_type)}"
                ),
                signer=signer,
                stamp_style=StaticStampStyle(
                    background=PdfImage(Image.open(io.BytesIO(signature_image))),
                    border_width=0
                )
            )

            pdf_signer.sign_pdf(writer, output=output_pdf, existing_fields_only=False, in_place=True)
            output_pdf.seek(0)
            return output_pdf

        else:
            print(f"No P12 certificate for signatory {signatory.emp.id}, skipping cryptographic signing")
            return input_pdf_buffer

    except Exception as e:
        import traceback
        traceback.print_exc()
        return input_pdf_buffer




def encrypt_text(text):    
    key = settings.FERNET_KEY  
    fernet = Fernet(key)
    
    encrypted_data = fernet.encrypt(text.encode())
    return encrypted_data

def get_signatory_password(emp_id, current_user_password):
    try:
        signature = Signature.objects.filter(emp_id=emp_id).first()
        if signature and signature.p12_password_enc:
            return decrypt_text(signature.p12_password_enc)
        else:
            return current_user_password
    except Exception as e:
        return current_user_password


def decrypt_text(encrypted_data):
    key = settings.FERNET_KEY  
    fernet = Fernet(key)
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        raise