#!/usr/bin/env python3
"""Median time, allocated and retained memory per version and n; see benchkit.analyze.

Usage: python3 analyze.py [--save] [RUN_DIRECTORY or CSV ...] (default: latest jvm and retained runs)
--save writes summary.txt and summary.csv into each run directory.
"""
from run import BENCHMARK, HERE, benchkit

benchkit.analyze_main(BENCHMARK, HERE)
