import datetime

from dateutil.relativedelta import relativedelta


def get_start_of_year(date: datetime.date):
    return date.replace(month=1, day=1)


def get_end_of_year(date: datetime.date):
    return date.replace(month=1, day=1) + relativedelta(years=1)


def get_start_of_month(date: datetime.date):
    return date.replace(day=1)


def get_end_of_month(date: datetime.date):
    return date.replace(day=1) + relativedelta(months=1)
