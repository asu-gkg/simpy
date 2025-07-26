# Binary tree topology class - corresponds to topology/BinaryTree.hh/cc in SimAI

from typing import Dict, Optional
from enum import Enum
import math
from .basic_logical_topology import BasicLogicalTopology
from .node import Node


class BinaryTree(BasicLogicalTopology):
    """Binary tree topology implementation
    
    Corresponds to topology/BinaryTree.hh/cc in SimAI
    """
    
    class TreeType(Enum):
        """Tree organization types"""
        RootMax = "RootMax"
        RootMin = "RootMin"
    
    class Type(Enum):
        """Node types in the tree"""
        Leaf = "Leaf"
        Root = "Root"
        Intermediate = "Intermediate"
    
    def __init__(
        self,
        node_id: int,
        tree_type: 'BinaryTree.TreeType',
        total_tree_nodes: int,
        start: int,
        stride: int
    ):
        """Initialize binary tree topology
        
        Args:
            node_id: This node's ID
            tree_type: Type of tree organization
            total_tree_nodes: Total number of nodes in the tree
            start: Starting node ID
            stride: Stride between node IDs
        """
        super().__init__(BasicLogicalTopology.BasicTopology.BinaryTree)
        
        self.total_tree_nodes = total_tree_nodes
        self.start = start
        self.tree_type = tree_type
        self.stride = stride
        self.tree: Optional[Node] = None
        self.node_list: Dict[int, Node] = {}
        
        # Initialize the tree structure
        self._build_tree_structure()
    
    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in dimension
        
        Args:
            dimension: Dimension index (should be 0 for tree)
            
        Returns:
            Total nodes in the tree
        """
        return self.total_tree_nodes
    
    def _build_tree_structure(self) -> None:
        """Build the binary tree structure"""
        if self.total_tree_nodes <= 0:
            return
        
        # Calculate tree depth
        depth = int(math.ceil(math.log2(self.total_tree_nodes + 1)))
        
        # Initialize root
        root_id = self.start if self.tree_type == BinaryTree.TreeType.RootMin else self.start + (self.total_tree_nodes - 1) * self.stride
        self.tree = self.initialize_tree(depth, None)
        
        # Build tree recursively
        self.build_tree(self.tree)
    
    def initialize_tree(self, depth: int, parent: Optional[Node]) -> Node:
        """Initialize tree structure recursively
        
        Args:
            depth: Remaining depth to build
            parent: Parent node
            
        Returns:
            Root of the subtree
        """
        if depth <= 0:
            return None
        
        # Create node with temporary ID
        node = Node(0, parent)
        
        if depth > 1:
            # Create children
            node.left_child = self.initialize_tree(depth - 1, node)
            node.right_child = self.initialize_tree(depth - 1, node)
        
        return node
    
    def build_tree(self, node: Optional[Node]) -> None:
        """Build tree with proper node IDs
        
        Args:
            node: Current node to process
        """
        if node is None:
            return
        
        # Assign proper ID based on tree type and position
        # This is a simplified assignment - actual implementation may vary
        node_count = len(self.node_list)
        if self.tree_type == BinaryTree.TreeType.RootMin:
            node.id = self.start + node_count * self.stride
        else:
            node.id = self.start + (self.total_tree_nodes - 1 - node_count) * self.stride
        
        # Add to node list
        self.node_list[node.id] = node
        
        # Recursively build children
        self.build_tree(node.left_child)
        self.build_tree(node.right_child)
    
    def get_parent_id(self, node_id: int) -> int:
        """Get parent node ID
        
        Args:
            node_id: Node ID to find parent for
            
        Returns:
            Parent node ID, or -1 if no parent
        """
        if node_id not in self.node_list:
            return -1
        
        node = self.node_list[node_id]
        return node.parent.id if node.parent else -1
    
    def get_left_child_id(self, node_id: int) -> int:
        """Get left child node ID
        
        Args:
            node_id: Node ID to find left child for
            
        Returns:
            Left child node ID, or -1 if no left child
        """
        if node_id not in self.node_list:
            return -1
        
        node = self.node_list[node_id]
        return node.left_child.id if node.left_child else -1
    
    def get_right_child_id(self, node_id: int) -> int:
        """Get right child node ID
        
        Args:
            node_id: Node ID to find right child for
            
        Returns:
            Right child node ID, or -1 if no right child
        """
        if node_id not in self.node_list:
            return -1
        
        node = self.node_list[node_id]
        return node.right_child.id if node.right_child else -1
    
    def get_node_type(self, node_id: int) -> 'BinaryTree.Type':
        """Get node type (root, leaf, or intermediate)
        
        Args:
            node_id: Node ID to check
            
        Returns:
            Node type
        """
        if node_id not in self.node_list:
            return BinaryTree.Type.Leaf  # Default
        
        node = self.node_list[node_id]
        
        if node.parent is None:
            return BinaryTree.Type.Root
        elif node.left_child is None and node.right_child is None:
            return BinaryTree.Type.Leaf
        else:
            return BinaryTree.Type.Intermediate
    
    def is_enabled(self, node_id: int) -> bool:
        """Check if a node is enabled based on stride
        
        Args:
            node_id: Node ID to check
            
        Returns:
            True if node is enabled
        """
        return node_id % self.stride == 0
    
    def print(self, node: Optional[Node]) -> None:
        """Print tree structure (for debugging)
        
        Args:
            node: Node to print from
        """
        if node is None:
            return
        
        print(f"Node {node.id}")
        if node.left_child:
            print(f"  Left: {node.left_child.id}")
            self.print(node.left_child)
        if node.right_child:
            print(f"  Right: {node.right_child.id}")
            self.print(node.right_child) 