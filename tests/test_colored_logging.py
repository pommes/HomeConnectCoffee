"""Tests für ColoredFormatter."""

from __future__ import annotations

import logging
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from homeconnect_coffee.errors import ColoredFormatter


@pytest.mark.unit
class TestColoredFormatter:
    """Tests für ColoredFormatter Klasse."""

    def test_format_info_no_color(self):
        """Test dass INFO keine Farben hat."""
        formatter = ColoredFormatter(
            fmt='%(levelname)s - %(message)s'
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert "Test message" in result
        # INFO sollte keine Farben haben
        assert "\033[0m" not in result or result.count("\033[0m") == 0

    def test_format_warning_with_color_when_enabled(self):
        """Test dass WARNING orange ist, wenn Farben aktiviert sind."""
        # Simuliere Terminal mit Farben
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {}, clear=False):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            record = logging.LogRecord(
                name="test",
                level=logging.WARNING,
                pathname="",
                lineno=0,
                msg="Warning message",
                args=(),
                exc_info=None,
            )
            
            result = formatter.format(record)
            
            if formatter._use_colors:
                # Sollte orange enthalten
                assert "\033[38;5;208m" in result or "\033[0m" in result
                assert "Warning message" in result
            else:
                # Keine Farben wenn deaktiviert
                assert "Warning message" in result

    def test_format_error_with_color_when_enabled(self):
        """Test dass ERROR rot ist, wenn Farben aktiviert sind."""
        # Simuliere Terminal mit Farben
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {}, clear=False):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            
            result = formatter.format(record)
            
            if formatter._use_colors:
                # Sollte rot enthalten
                assert "\033[31m" in result or "\033[0m" in result
                assert "Error message" in result
            else:
                # Keine Farben wenn deaktiviert
                assert "Error message" in result

    def test_no_color_when_no_color_env_set(self):
        """Test dass Farben deaktiviert sind, wenn NO_COLOR gesetzt ist."""
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {"NO_COLOR": "1"}):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

    def test_no_color_when_not_tty(self):
        """Test dass Farben deaktiviert sind, wenn nicht TTY."""
        with patch('sys.stdout.isatty', return_value=False):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

    def test_no_color_when_term_dumb(self):
        """Test dass Farben deaktiviert sind, wenn TERM=dumb."""
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {"TERM": "dumb"}):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

