"""
Barcode generation and scanning service
"""
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
from django.http import HttpResponse


class BarcodeService:
    """Barcode generation service"""
    
    @staticmethod
    def generate_barcode(data, barcode_type='code128'):
        """
        Generate barcode image
        
        Args:
            data: Data to encode (SKU, serial number, etc.)
            barcode_type: Type of barcode (code128, ean13, etc.)
        
        Returns:
            BytesIO buffer with barcode image
        """
        try:
            # Get barcode class
            barcode_class = barcode.get_barcode_class(barcode_type)
            
            # Create barcode instance
            barcode_instance = barcode_class(data, writer=ImageWriter())
            
            # Generate barcode to buffer
            buffer = BytesIO()
            barcode_instance.write(buffer)
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            raise ValueError(f"Barcode generation failed: {str(e)}")
    
    @staticmethod
    def generate_qrcode(data):
        """
        Generate QR code image
        
        Args:
            data: Data to encode (URL, JSON, text)
        
        Returns:
            BytesIO buffer with QR code image
        """
        try:
            import qrcode
            from qrcode.image.pure import PyPNGImage
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            raise ValueError(f"QR code generation failed: {str(e)}")
    
    @staticmethod
    def generate_item_barcode_response(item):
        """Generate barcode for an item and return HTTP response"""
        buffer = BarcodeService.generate_barcode(item.sku)
        
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{item.sku}_barcode.png"'
        return response
    
    @staticmethod
    def generate_item_qrcode_response(item):
        """Generate QR code for an item and return HTTP response"""
        import json
        
        # Create JSON data for item
        data = json.dumps({
            'sku': item.sku,
            'name': item.name,
            'category': item.category.name if item.category else None,
            'unit': item.unit
        })
        
        buffer = BarcodeService.generate_qrcode(data)
        
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{item.sku}_qrcode.png"'
        return response

