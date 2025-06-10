# ui/pages/__init__.py
"""
ページモジュール

各ページの描画ロジックを含むモジュール群です。
各ページは独立したモジュールとして実装され、
共通のインターフェースを持ちます。
"""

from . import (
    dashboard_page,
    upload_page,
    data_management_page,
    hospital_page,
    department_page,
    surgeon_page,
    prediction_page
)

__all__ = [
    'dashboard_page',
    'upload_page', 
    'data_management_page',
    'hospital_page',
    'department_page',
    'surgeon_page',
    'prediction_page'
]