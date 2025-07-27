#!/usr/bin/env python3
"""
NS3 Network Frontend - corresponds to ns3 module in SimAI

Provides NS3-based network simulation backend for SimAI
"""

from .common import NS3_AVAILABLE, GPUType
from .AstraSimNetwork import ASTRASimNetwork, sim_event, main, user_param
from .entry import task1, cleanup_hash_maps

__all__ = [
    'NS3_AVAILABLE',
    'GPUType', 
    'ASTRASimNetwork',
    'sim_event',
    'task1',
    'cleanup_hash_maps',
    'main',
    'user_param'
]