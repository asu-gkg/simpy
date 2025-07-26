# DoubleBinaryTreeAllReduce collective algorithm - corresponds to collective/DoubleBinaryTreeAllReduce.hh/cc in SimAI

from typing import TYPE_CHECKING
from enum import Enum
from .algorithm import Algorithm
from ..common import ComType, EventType
from ..callable import CallData

if TYPE_CHECKING:
    from ..topology.binary_tree import BinaryTree


class DoubleBinaryTreeAllReduce(Algorithm):
    """DoubleBinaryTreeAllReduce collective communication algorithm
    
    Corresponds to collective/DoubleBinaryTreeAllReduce.hh/cc in SimAI
    """
    
    class State(Enum):
        """State enumeration for the algorithm"""
        Begin = "Begin"
        WaitingForTwoChildData = "WaitingForTwoChildData"
        WaitingForOneChildData = "WaitingForOneChildData"
        SendingDataToParent = "SendingDataToParent"
        WaitingDataFromParent = "WaitingDataFromParent"
        SendingDataToChilds = "SendingDataToChilds"
        End = "End"
    
    def __init__(self,
                 id: int,
                 layer_num: int,
                 tree: 'BinaryTree',
                 data_size: int,
                 boost_mode: bool):
        """Initialize DoubleBinaryTreeAllReduce algorithm
        
        Args:
            id: Node ID
            layer_num: Layer number
            tree: Binary tree topology
            data_size: Data size
            boost_mode: Whether boost mode is enabled
        """
        super().__init__(layer_num)
        
        # Basic properties
        self.id = id
        self.logicalTopology = tree
        self.data_size = data_size
        self.state = self.State.Begin
        self.reductions = 0
        
        # Tree structure information
        self.parent = tree.get_parent_id(id)
        self.left_child = tree.get_left_child_id(id)
        self.right_child = tree.get_right_child_id(id)
        self.type = tree.get_node_type(id)
        
        # Algorithm properties
        self.final_data_size = data_size
        self.comType = ComType.All_Reduce
        self.name = Algorithm.Name.DoubleBinaryTree
        self.enabled = True
        
        if boost_mode:
            self.enabled = tree.is_enabled(id)
    
    def run(self, event: EventType, data: CallData) -> None:
        """Run the DoubleBinaryTreeAllReduce algorithm
        
        Args:
            event: Event type
            data: Call data
        """
        # Leaf node states
        if (self.state == self.State.Begin and 
            self.type == "Leaf"):  # leaf.1
            # Send data to MA (Memory Access)
            self._create_packet_bundle_to_ma(False, False)
            self.state = self.State.SendingDataToParent
            return
            
        elif (self.state == self.State.SendingDataToParent and 
              self.type == "Leaf"):  # leaf.3
            # Send to parent and wait for response
            self._send_to_parent()
            self._recv_from_parent()
            self.state = self.State.WaitingDataFromParent
            return
            
        elif (self.state == self.State.WaitingDataFromParent and 
              self.type == "Leaf"):  # leaf.4
            # Send data to NPU (Neural Processing Unit)
            self._create_packet_bundle_to_npu(False, False)
            self.state = self.State.End
            return
            
        elif (self.state == self.State.End and 
              self.type == "Leaf"):  # leaf.5
            self.exit()
            return
        
        # Intermediate node states
        elif (self.state == self.State.Begin and 
              self.type == "Intermediate"):  # int.1
            # Receive from both children
            self._recv_from_child(self.left_child)
            self._recv_from_child(self.right_child)
            self.state = self.State.WaitingForTwoChildData
            return
            
        elif (self.state == self.State.WaitingForTwoChildData and 
              self.type == "Intermediate" and 
              event == EventType.PacketReceived):  # int.2
            # Process first child data
            self._create_packet_bundle_to_npu(True, False)
            self.state = self.State.WaitingForOneChildData
            return
            
        elif (self.state == self.State.WaitingForOneChildData and 
              self.type == "Intermediate" and 
              event == EventType.PacketReceived):  # int.3
            # Process second child data
            self._create_packet_bundle_to_npu(True, True)
            self.state = self.State.SendingDataToParent
            return
            
        elif (self.reductions < 1 and 
              self.type == "Intermediate" and 
              event == EventType.General):  # int.4
            self.reductions += 1
            return
            
        elif (self.state == self.State.SendingDataToParent and 
              self.type == "Intermediate"):  # int.5
            # Send to parent and wait for response
            self._send_to_parent()
            self._recv_from_parent()
            self.state = self.State.WaitingDataFromParent
            
        elif (self.state == self.State.WaitingDataFromParent and 
              self.type == "Intermediate" and 
              event == EventType.PacketReceived):  # int.6
            # Process parent data
            self._create_packet_bundle_to_npu(True, True)
            self.state = self.State.SendingDataToChilds
            return
            
        elif (self.state == self.State.SendingDataToChilds and 
              self.type == "Intermediate"):
            # Send to both children
            self._send_to_child(self.left_child)
            self._send_to_child(self.right_child)
            self.exit()
            return
        
        # Root node states
        elif (self.state == self.State.Begin and 
              self.type == "Root"):  # root.1
            only_child_id = self.left_child if self.left_child >= 0 else self.right_child
            self._recv_from_child(only_child_id)
            self.state = self.State.WaitingForOneChildData
            
        elif (self.state == self.State.WaitingForOneChildData and 
              self.type == "Root"):  # root.2
            self._create_packet_bundle_to_npu(True, True)
            self.state = self.State.SendingDataToChilds
            return
            
        elif (self.state == self.State.SendingDataToChilds and 
              self.type == "Root"):  # root.3
            only_child_id = self.left_child if self.left_child >= 0 else self.right_child
            self._send_to_child(only_child_id)
            self.exit()
            return
    
    def _create_packet_bundle_to_ma(self, processed: bool, send_back: bool) -> None:
        """Create packet bundle to send to MA
        
        Args:
            processed: Whether data is processed
            send_back: Whether to send back
        """
        # Simulate PacketBundle creation and sending to MA
        # In real implementation, this would create a PacketBundle object
        pass
    
    def _create_packet_bundle_to_npu(self, processed: bool, send_back: bool) -> None:
        """Create packet bundle to send to NPU
        
        Args:
            processed: Whether data is processed
            send_back: Whether to send back
        """
        # Simulate PacketBundle creation and sending to NPU
        # In real implementation, this would create a PacketBundle object
        pass
    
    def _send_to_parent(self) -> None:
        """Send data to parent node"""
        if self.stream and hasattr(self.stream, 'owner'):
            # Simulate front_end_sim_send to parent
            # In real implementation, this would call the network send API
            pass
    
    def _recv_from_parent(self) -> None:
        """Receive data from parent node"""
        if self.stream and hasattr(self.stream, 'owner'):
            # Simulate front_end_sim_recv from parent
            # In real implementation, this would call the network receive API
            pass
    
    def _send_to_child(self, child_id: int) -> None:
        """Send data to child node
        
        Args:
            child_id: Child node ID
        """
        if self.stream and hasattr(self.stream, 'owner'):
            # Simulate front_end_sim_send to child
            # In real implementation, this would call the network send API
            pass
    
    def _recv_from_child(self, child_id: int) -> None:
        """Receive data from child node
        
        Args:
            child_id: Child node ID
        """
        if self.stream and hasattr(self.stream, 'owner'):
            # Simulate front_end_sim_recv from child
            # In real implementation, this would call the network receive API
            pass 