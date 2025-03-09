from io import BytesIO

from pdf2image import convert_from_path

from apps.credits.models import ApplicationFaceMatchPhoto
from config import celery_app


@celery_app.task()
def convert_pdf_to_image(biometric_images_id: int, dpi=500):
    biometric_images = ApplicationFaceMatchPhoto.objects.get(id=biometric_images_id)

    page = convert_from_path(biometric_images.document_file.path, dpi)[0]
    image_bytes = BytesIO()
    page.save(image_bytes, format='JPEG')
    image_file = BytesIO(image_bytes.getvalue())

    biometric_images.document_photo.save("document_photo.jpg", image_file)