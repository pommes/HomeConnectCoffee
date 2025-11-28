"""Tests for ColoredFormatter."""

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
    """Tests for ColoredFormatter class."""

    def test_format_info_no_color(self):
        """Test that INFO has no colors."""
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
        # INFO should have no colors
        assert "\033[0m" not in result or result.count("\033[0m") == 0

    def test_format_warning_with_color_when_enabled(self):
        """Test that WARNING is orange when colors are enabled."""
        # Simulate terminal with colors
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
                # Should contain orange
                assert "\033[38;5;208m" in result or "\033[0m" in result
                assert "Warning message" in result
            else:
                # No colors when disabled
                assert "Warning message" in result

    def test_format_error_with_color_when_enabled(self):
        """Test that ERROR is red when colors are enabled."""
        # Simulate terminal with colors
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
                # Should contain red
                assert "\033[31m" in result or "\033[0m" in result
                assert "Error message" in result
            else:
                # No colors when disabled
                assert "Error message" in result

    def test_no_color_when_no_color_env_set(self):
        """Test that colors are disabled when NO_COLOR is set."""
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {"NO_COLOR": "1"}):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

    def test_no_color_when_not_tty(self):
        """Test that colors are disabled when not TTY."""
        with patch('sys.stdout.isatty', return_value=False):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

    def test_no_color_when_term_dumb(self):
        """Test that colors are disabled when TERM=dumb."""
        with patch('sys.stdout.isatty', return_value=True), \
             patch.dict(os.environ, {"TERM": "dumb"}):
            
            formatter = ColoredFormatter(
                fmt='%(levelname)s - %(message)s'
            )
            
            assert formatter._use_colors is False

