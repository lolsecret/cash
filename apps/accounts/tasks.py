import io

from PyPDF2 import PdfReader
from celery import shared_task

from .models import ProfilePersonalRecord
from .services import AccountService
from ..api.user.auth.utils import KaspiBankStatementParser


@shared_task
def update_client_info(**kwargs):
    """Фоновое обновление данных"""
    service = AccountService()
    service.get_client_info(**kwargs)


@shared_task
def process_bank_statement(personal_record_id, file_path):
    """
    Асинхронная задача для обработки банковской выписки.

    Args:
        personal_record_id (int): ID записи профиля
        file_path (str): Путь к сохраненному файлу выписки
    """
    try:
        # Получаем запись профиля
        personal_record = ProfilePersonalRecord.objects.get(pk=personal_record_id)

        # Извлекаем текст из PDF
        with open(file_path, 'rb') as pdf_file:
            pdf_data = io.BytesIO(pdf_file.read())
            reader = PdfReader(pdf_data)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

        # Анализируем выписку
        parser = KaspiBankStatementParser(text)
        result = parser.parse()

        # Сохраняем результаты
        personal_record.average_monthly_income = result['average_monthly_income']
        personal_record.income_calculated_at = result['calculation_date']
        personal_record.save(update_fields=[
            'average_monthly_income',
            'income_calculated_at',
        ])

    except Exception as e:

        # Логгирование ошибки
        print(f"Ошибка при обработке выписки: {e}")
        # В продакшн здесь должен быть вызов logger.error()
