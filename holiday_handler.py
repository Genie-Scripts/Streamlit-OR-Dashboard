import jpholiday

def is_weekday(date):
    """与えられた日付が平日かどうかを判定（祝日と年末年始を除外）"""
    if date.weekday() >= 5:  # 土日
        return False
    if jpholiday.is_holiday(date):  # 祝日
        return False
    if (date.month == 12 and date.day >= 29) or (date.month == 1 and date.day <= 3):  # 年末年始
        return False
    return True