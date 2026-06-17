from __future__ import annotations


def test_dashboard_module_imports():
    from apps.web.ui import dashboard

    assert hasattr(dashboard, "dashboard_page")


def test_mount_ui_imports_dashboard():
    from apps.web.ui.app import mount_ui

    mount_ui()
    from apps.web.ui import dashboard

    assert dashboard.dashboard_page is not None
