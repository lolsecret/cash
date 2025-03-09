import re
from decimal import Decimal, DecimalException
from datetime import datetime
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class KaspiBankStatementParser:
    """
    Универсальный парсер для банковской выписки Kaspi Bank.
    Извлекает операции пополнения и рассчитывает средний ежемесячный доход.
    """

    def __init__(self, file_content):
        """
        Инициализировать парсер с содержимым файла выписки.

        Args:
            file_content (str): Содержимое файла выписки в текстовом формате
        """
        self.content = file_content
        self.excluded_sources = ["С Kaspi Депозита", "Со своего Счета в Kaspi Pay"]

    def parse(self):
        """
        Парсинг выписки и расчет среднего дохода.

        Returns:
            dict: Результаты анализа выписки
        """
        # Определение периода выписки
        period_match = re.search(r'период с (\d{2}\.\d{2}\.\d{2}) по (\d{2}\.\d{2}\.\d{2})', self.content)
        if period_match:
            start_date = datetime.strptime(period_match.group(1), '%d.%m.%y')
            end_date = datetime.strptime(period_match.group(2), '%d.%m.%y')

            # Расчет полных месяцев между датами
            months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month

            # Если разница в месяцах равна 0, но даты разные, считаем как 1 месяц
            period_months = max(1, months_diff)
        else:
            # Если период не найден, используем стандартный 1 месяц
            period_months = 1

        # Два варианта извлечения транзакций для большей надежности
        # 1. Поиск по таблице операций
        transactions = []

        # Более устойчивый паттерн для извлечения строк из таблицы
        table_pattern = r'(\d{2}\.\d{2}\.\d{2})\s+([-+])\s+([\d\s]+,\d{2})\s+₸\s+(\w+)\s+(.*?)(?=\n\d{2}\.\d{2}\.\d{2}|\n?$)'
        transactions_raw = re.findall(table_pattern, self.content, re.DOTALL | re.MULTILINE)

        # Обработка извлеченных транзакций
        for date, sign, amount, operation, details in transactions_raw:
            amount_str = amount.replace(' ', '').replace(',', '.')
            try:
                amount_decimal = Decimal(amount_str)
                transactions.append({
                    'date': date,
                    'sign': sign,
                    'amount': amount_decimal,
                    'operation': operation,
                    'details': details.strip()
                })
            except (ValueError, DecimalException):
                logger.warning(f"Некорректная сумма: {amount_str} в строке {date} {sign} {amount} {operation}")

        # Фильтрация и обработка транзакций
        incomes = []

        # Находим начальный баланс
        initial_balance_pattern = r'Доступно на \d{2}\.\d{2}\.\d{2}[:]?\s+([+\-])\s+([\d\s]+,\d{2})\s+₸'
        initial_balance_match = re.search(initial_balance_pattern, self.content)
        initial_balance = None

        if initial_balance_match:
            try:
                balance_amount = initial_balance_match.group(2).replace(' ', '').replace(',', '.')
                initial_balance = Decimal(balance_amount)
            except (ValueError, DecimalException):
                logger.warning(f"Не удалось распознать начальный баланс: {initial_balance_match.group(2)}")

        # Обработка транзакций для выделения реальных поступлений
        for trans in transactions:
            # Пропускаем транзакции с нулевой суммой
            if trans['amount'] == 0:
                continue

            # Проверяем, не является ли это начальным балансом
            if initial_balance is not None and trans['amount'] == initial_balance:
                continue

            # Обрабатываем только поступления
            if trans['sign'] == '+':
                details = trans['details']

                # Исключаем поступления с Kaspi Депозита и другие исключаемые источники
                excluded = False
                for source in self.excluded_sources:
                    if source.lower() in details.lower():
                        excluded = True
                        break

                if excluded:
                    continue

                # Проверяем тип операции
                if trans['operation'] == 'Пополнение':
                    # Дополнительные проверки для Пополнений
                    if "Остаток" not in details and "Доступно" not in details:
                        incomes.append(trans)
                elif trans['operation'] == 'Покупка':
                    # Это возврат средств, игнорируем как неявный источник дохода
                    continue
                else:
                    # Другие операции со знаком + могут быть доходом
                    # Проверяем по содержимому
                    if "зарплат" in details.lower() or "перевод" in details.lower():
                        incomes.append(trans)

        # Расчет дохода
        total_income = sum(income['amount'] for income in incomes)
        average_monthly_income = total_income / Decimal(period_months)

        # Минимальное логирование для продакшена
        logger.info(f"Период выписки: {period_months} месяц(ев)")
        logger.info(f"Найдено транзакций: {len(transactions)}")
        logger.info(f"Учтено поступлений: {len(incomes)}")
        logger.info(f"Итоговая сумма поступлений: {total_income}")
        logger.info(f"Средний ежемесячный доход: {average_monthly_income}")

        return {
            'incomes': incomes,
            'total_income': total_income,
            'period_months': period_months,
            'average_monthly_income': average_monthly_income,
            'calculation_date': timezone.now()
        }
