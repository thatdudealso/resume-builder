from __future__ import annotations

from apps.web.ui.app import _RUN_ERROR_GENERIC, _sanitize_run_error


def test_sanitize_run_error_hides_short_provider_message():
    message = "Provider timed out after 3 retries"
    assert _sanitize_run_error(message) == _RUN_ERROR_GENERIC


def test_sanitize_run_error_replaces_traceback_text():
    message = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: boom'
    assert _sanitize_run_error(message) == _RUN_ERROR_GENERIC


def test_sanitize_run_error_hides_long_message():
    message = "x" * 161
    assert _sanitize_run_error(message) == _RUN_ERROR_GENERIC


def test_sanitize_run_error_hides_message_at_boundary_length():
    message = "x" * 160
    assert _sanitize_run_error(message) == _RUN_ERROR_GENERIC


def test_sanitize_run_error_handles_empty_message():
    assert _sanitize_run_error("") == _RUN_ERROR_GENERIC


def test_sanitize_run_error_handles_whitespace_only_message():
    assert _sanitize_run_error("   ") == _RUN_ERROR_GENERIC
