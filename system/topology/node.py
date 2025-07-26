# Node classes - corresponds to topology/Node.hh and ComputeNode.hh in SimAI

from typing import Optional


class ComputeNode:
    """Compute node base class
    
    Corresponds to topology/ComputeNode.hh in SimAI
    """
    pass


class Node(ComputeNode):
    """Node class for tree topologies
    
    Corresponds to topology/Node.hh in SimAI
    """
    
    def __init__(
        self, 
        node_id: int, 
        parent: Optional['Node'] = None, 
        left_child: Optional['Node'] = None, 
        right_child: Optional['Node'] = None
    ):
        """Initialize node
        
        Args:
            node_id: Unique identifier for the node
            parent: Parent node (None for root)
            left_child: Left child node
            right_child: Right child node
        """
        super().__init__()
        self.id = node_id
        self.parent = parent
        self.left_child = left_child
        self.right_child = right_child 