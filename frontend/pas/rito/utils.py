import base64
import io
import os
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
from backend.models import Designation



def get_travel_signatory_role_name(signatory_type):
    roles = {
        0: "Self Approval",
        1: "Requested By", 
        2: "Noted By",
        3: "Approved By",
        4: "RAMS Approval"
    }
    return roles.get(signatory_type, "Signatory")


def get_travel_signature_positions():
    return {
        0: (100, 600, 200, 650),    # Self Approval/Requester x1,y1,x2,y2
        1: (100, 550, 200, 600),    # Requested By 
        2: (65, 175, 170, 201),    # Noted By
        # 3: (240, 240, 345, 290),    # Approved By
        4: (90, 175, 195, 201),    # RAMS Approval
    }
    
def multiple_travel_signatories(input_pdf_buffer, signature_record, password, signatory, signature_index, dynamic_positions=None, target_page=0):
    try:
        if signatory.signatory_type != 3:
            print(f"Skipping non-RD signatory (type {signatory.signatory_type})")
            return input_pdf_buffer
        
        has_p12 = signature_record.p12_file and os.path.exists(signature_record.p12_file.path)
        
        if has_p12:
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

            signeddate = signatory.date.strftime('%Y-%m-%d %H:%M') if signatory.date else datetime.now().strftime('%Y-%m-%d %H:%M')

            signature_base64 = generate_validated_signature_stamp(signature_record, signeddate,  certname )
            signature_image = base64.b64decode(signature_base64)

            sig_positions = get_travel_signature_positions()
            
            if dynamic_positions and 'rd_signature' in dynamic_positions:
                rd_pos = dynamic_positions['rd_signature']
                box = (rd_pos['x1'], rd_pos['y1'], rd_pos['x2'], rd_pos['y2'])
            else:
                box = sig_positions.get( signatory.signatory_type,  (50, 400, 300, 455)  )

            input_pdf_buffer.seek(0)
            writer = IncrementalPdfFileWriter(input_pdf_buffer)
            output_pdf = io.BytesIO()

            timestamp = int(datetime.now().timestamp())
            field_name = f"TravelSig_RD_{signatory.emp.id}_{timestamp}"

            append_signature_field(writer, SigFieldSpec(sig_field_name=field_name, on_page=target_page, box=box))

            pdf_signer = PdfSigner(
                signature_meta=PdfSignatureMetadata(
                    field_name=field_name,
                    name=certname,
                    location="Travel Order Management System",
                    reason=f"Travel Order Approval - {get_travel_signatory_role_name(signatory.signatory_type)}"
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
            return input_pdf_buffer

    except Exception as e:
        import traceback
        traceback.print_exc()
        return input_pdf_buffer
    
    
def generate_validated_signature_stamp(signature, signed_date, cert_name):
    try:
        from PIL import Image, ImageDraw, ImageFont
    
        import io, base64, os

        def load_font(size, bold=False):
            try:
                if bold:
                    return ImageFont.truetype("arialbd.ttf", size=size)
                return ImageFont.truetype("arial.ttf", size=size)
            except:
                return ImageFont.load_default()
            
            

        # === SPACING CONTROLS (adjust here if needed) ===
        approval_text_top_margin = 5       # Space above "Approved by"
        approval_to_signature_gap = 5      # Gap between "Approved by" and signature
        signature_to_name_gap = 15          # Gap between signature and name
        name_to_designation_gap = 10         # Gap between name and designation
        bottom_padding = 5                # Compress bottom space
        # ===============================================

        # Font sizes
        approval_font = load_font(25)
        name_font = load_font(24, bold=True)
        designation_font = load_font(23)

        canvas = None
        draw = None

        if signature.signature_img and os.path.exists(signature.signature_img.path):
            try:
                sig_img = Image.open(signature.signature_img.path).convert("RGBA")

                sig_width = 385
                sig_height = 125
                sig_img = sig_img.resize((sig_width, sig_height), Image.Resampling.LANCZOS)

                canvas_width = sig_width
                canvas_temp = Image.new("RGBA", (canvas_width, 1000), (255, 255, 255, 255))
                draw_temp = ImageDraw.Draw(canvas_temp)

                # Draw "Approved by"
                approval_text = "Approved by"
                text_bbox = draw_temp.textbbox((0, 0), approval_text, font=approval_font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # Get approver name
                if hasattr(signature, 'emp') and hasattr(signature.emp, 'pi') and hasattr(signature.emp.pi, 'user'):
                    user = signature.emp.pi.user
                    first = user.first_name or ""
                    middle = (user.middle_name[0] + ".") if user.middle_name else ""
                    last = user.last_name or ""
                    approver_name = f"{first} {middle} {last}".strip().upper()
                else:
                    approver_name = cert_name.upper()

                name_bbox = draw_temp.textbbox((0, 0), approver_name, font=name_font)
                name_height_actual = name_bbox[3] - name_bbox[1]

                try:
                    # from backend.models import Designation
                    designation_obj = Designation.objects.filter(name='Regional Director').first()
                    designation_text = designation_obj.name if designation_obj else "Regional Director"
                except:
                    designation_text = "Regional Director"

                des_bbox = draw_temp.textbbox((0, 0), designation_text, font=designation_font)
                designation_height = des_bbox[3] - des_bbox[1]

                # Compute final height using actual measurements
                canvas_height = int(
                    approval_text_top_margin +
                    text_height +
                    approval_to_signature_gap +
                    sig_height +
                    signature_to_name_gap +
                    name_height_actual +
                    name_to_designation_gap +
                    designation_height +
                    bottom_padding
                )

                # Now create final canvas
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
                draw = ImageDraw.Draw(canvas)

                # Draw "Approved by"
                text_x = (canvas_width - text_width) // 2
                text_y = approval_text_top_margin
                draw.text((text_x, text_y), approval_text, fill=(0, 0, 0), font=approval_font)

                # Paste signature
                signature_y = text_y + text_height + approval_to_signature_gap
                canvas.paste(sig_img, (0, signature_y), mask=sig_img)

                # Draw approver name
                name_x = (canvas_width - (name_bbox[2] - name_bbox[0])) // 2
                name_y = signature_y + sig_height + signature_to_name_gap
                draw.text((name_x, name_y), approver_name, fill=(0, 0, 0), font=name_font)

                # Draw designation
                des_x = (canvas_width - (des_bbox[2] - des_bbox[0])) // 2
                designation_y = name_y + name_height_actual + name_to_designation_gap
                draw.text((des_x, designation_y), designation_text, fill=(0, 0, 0), font=designation_font)


            except Exception as e:
                print(f"Error loading signature image: {e}")
                import traceback
                traceback.print_exc()

        # Fallback if no canvas created
        if canvas is None:
            canvas_width, canvas_height = 700, 600
            canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
            draw = ImageDraw.Draw(canvas)
            draw.text((canvas_width // 2 - 80, canvas_height // 2),
                      "No Signature", fill=(128, 128, 128), font=approval_font)

        # Convert to base64
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return img_str

    except Exception as e:
        print(f"Error generating validated signature stamp: {e}")
        import traceback
        traceback.print_exc()

        try:
            placeholder = Image.new("RGBA", (700, 600), (255, 255, 255, 255))
            draw = ImageDraw.Draw(placeholder)
            font_placeholder = load_font(40, bold=True)
            draw.text((250, 280), "No Signature", fill=(0, 0, 0), font=font_placeholder)

            buffer = io.BytesIO()
            placeholder.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode()
        except:
            return ""
        
    



# def generate_validated_signature_stamp(signature, signed_date, cert_name):
#     try:
#         from PIL import Image, ImageDraw, ImageFont
#         import io, base64, os

#         # Load font helper
#         def load_font(size, bold=False):
#             try:
#                 if bold:
#                     return ImageFont.truetype("arialbd.ttf", size=size)
#                 return ImageFont.truetype("arial.ttf", size=size)
#             except:
#                 return ImageFont.load_default()

#         # Enhanced font sizes for better readability
#         header_font_size = 50  # "Approved by:"
#         name_font_size = 40    # Approver name (most prominent)
#         designation_font_size = 30  # Position/designation
        
#         font_header = load_font(header_font_size, bold=True)
#         font_name = load_font(name_font_size, bold=True)
#         font_designation = load_font(designation_font_size)

#         # Calculate canvas dimensions with better spacing
#         padding_top = 45       # Space for "Approved by:"
#         padding_middle = 25    # Space between header and signature
#         sig_height = 250       # Signature image height (increased)
#         sig_width = 350        # Signature image width (increased)
#         padding_after_sig = 35 # Space between signature and name
#         name_height = 60       # Approximate height for name
#         padding_after_name = 18 # Space between name and designation
#         designation_height = 30 # Approximate height for designation
#         padding_bottom = 30    # Bottom padding
        
#         canvas_width = sig_width + 120  # Add side padding
#         canvas_height = (padding_top + padding_middle + sig_height + 
#                         padding_after_sig + name_height + 
#                         padding_after_name + designation_height + padding_bottom)
        
#         # Create canvas with white background for visibility
#         canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
#         draw = ImageDraw.Draw(canvas)
        
#         # Optional: Add a subtle border for definition
#         border_color = (200, 200, 200, 255)
#         draw.rectangle([(2, 2), (canvas_width-3, canvas_height-3)], outline=border_color, width=2)

#         # Draw "Approved by:" text at the top
#         current_y = padding_top
#         approved_text = "Approved by:"
#         approved_bbox = draw.textbbox((0, 0), approved_text, font=font_header)
#         approved_width = approved_bbox[2] - approved_bbox[0]
#         approved_x = (canvas_width - approved_width) // 2
#         draw.text((approved_x, 15), approved_text, fill=(0, 0, 0, 255), font=font_header)

#         # Paste signature image in the middle
#         current_y = padding_top + padding_middle
#         sig_x = (canvas_width - sig_width) // 2
        
#         if signature.signature_img and os.path.exists(signature.signature_img.path):
#             try:
#                 sig_img = Image.open(signature.signature_img.path).convert("RGBA")
#                 # Maintain aspect ratio while resizing
#                 sig_img.thumbnail((sig_width, sig_height), Image.Resampling.LANCZOS)
                
#                 # Center the signature if it's smaller than expected
#                 actual_width, actual_height = sig_img.size
#                 sig_x_adjusted = sig_x + (sig_width - actual_width) // 2
#                 sig_y_adjusted = current_y + (sig_height - actual_height) // 2
                
#                 canvas.paste(sig_img, (sig_x_adjusted, sig_y_adjusted), mask=sig_img)
#             except Exception as e:
#                 print(f"Error loading signature image: {e}")
#                 # Draw placeholder text if signature fails to load
#                 draw.text((sig_x + 20, current_y + 60), "[Signature]", 
#                          fill=(128, 128, 128, 255), font=font_designation)

#         # Draw name below signature
#         current_y += sig_height + padding_after_sig
        
#         # Get approver's full name from signature record
#         if hasattr(signature, 'emp') and hasattr(signature.emp, 'pi') and hasattr(signature.emp.pi, 'user'):
#             user = signature.emp.pi.user
#             first = user.first_name or ""
#             middle = user.middle_name or ""
#             last = user.last_name or ""
#             approver_name = f"{first} {middle} {last}".strip()
#             # Remove extra spaces
#             approver_name = " ".join(approver_name.split())
#             approver_name = approver_name.upper()
#         else:
#             approver_name = cert_name.upper()
        
#         # Adjust font size if name is too long
#         max_text_width = canvas_width - 60
#         current_font = font_name
#         current_size = name_font_size
#         while current_size > 16:
#             name_bbox = draw.textbbox((0, 0), approver_name, font=current_font)
#             name_width = name_bbox[2] - name_bbox[0]
#             if name_width <= max_text_width:
#                 break
#             current_size -= 1
#             current_font = load_font(current_size, bold=True)
        
#         name_bbox = draw.textbbox((0, 0), approver_name, font=current_font)
#         name_width = name_bbox[2] - name_bbox[0]
#         name_x = (canvas_width - name_width) // 2
        
#         # Add underline effect for name
#         draw.text((name_x, current_y), approver_name, fill=(0, 0, 0, 255), font=current_font)
#         line_y = current_y + name_bbox[3] - name_bbox[1] + 2
#         draw.line([(name_x, line_y), (name_x + name_width, line_y)], 
#                  fill=(0, 0, 0, 255), width=2)

#         # Draw designation/position below name
#         current_y = line_y + padding_after_name + 5

#         # Get designation from signature record
#         designation_obj = Designation.objects.filter(name='Regional Director').first()
#         designation_text = designation_obj.name if designation_obj else "Regional Director"

#         # Adjust font size if designation is too long
#         current_font_des = font_designation
#         current_size_des = designation_font_size
#         while current_size_des > 14:
#             des_bbox = draw.textbbox((0, 0), designation_text, font=current_font_des)
#             des_width = des_bbox[2] - des_bbox[0]
#             if des_width <= max_text_width:
#                 break
#             current_size_des -= 1
#             current_font_des = load_font(current_size_des)

#         des_bbox = draw.textbbox((0, 0), designation_text, font=current_font_des)
#         des_width = des_bbox[2] - des_bbox[0]
#         des_x = (canvas_width - des_width) // 2
#         draw.text((des_x, current_y), designation_text, fill=(0, 0, 0, 255), font=current_font_des)


#         # Convert to base64
#         buffer = io.BytesIO()
#         canvas.save(buffer, format="PNG")
#         img_str = base64.b64encode(buffer.getvalue()).decode()

#         return img_str

#     except Exception as e:
#         print(f"Error generating validated signature stamp: {e}")
#         import traceback
#         traceback.print_exc()

#         try:
#             placeholder = Image.new("RGBA", (570, 390), (255, 255, 255, 255))
#             draw = ImageDraw.Draw(placeholder)
#             font_placeholder = load_font(20, bold=True)
#             draw.text((200, 180), "Signature Error", fill=(255, 0, 0, 255), font=font_placeholder)

#             buffer = io.BytesIO()
#             placeholder.save(buffer, format="PNG")
#             return base64.b64encode(buffer.getvalue()).decode()
#         except:
#             return ""