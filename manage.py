#!/usr/bin/env python
"""
Medical Search Platform - Django Management Script
Copyright (c) 2025 DRCI - CHU Clermont-Ferrand
All rights reserved.

Author: FIANKO Kossi Jean-Jacques Daniel
License: MIT License (see LICENSE file)
"""

import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
