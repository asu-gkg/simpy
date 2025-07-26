# NcclTreeFlowModel collective algorithm - corresponds to collective/NcclTreeFlowModel.hh/cc in SimAI

from typing import Dict, List, Set, Optional, Tuple, TYPE_CHECKING
import threading
import time
from collections import defaultdict, deque
from .algorithm import Algorithm
from ..common import ComType, EventType, InjectionPolicy, StreamState
from ..callable import CallData

if TYPE_CHECKING:
    from ..topology.ring_topology import RingTopology


class NcclTreeFlowModel(Algorithm):
    """NcclTreeFlowModel collective communication algorithm
    
    Corresponds to collective/NcclTreeFlowModel.hh/cc in SimAI
    Advanced flow model with tree-based communication patterns
    """
    
    # Class variable for critical section synchronization
    _g_flow_inCriticalSection = threading.Lock()
    
    def __init__(self,
                 com_type: ComType,
                 id: int,
                 layer_num: int,
                 ring_topology: 'RingTopology',
                 data_size: int,
                 direction: 'RingTopology.Direction',
                 injection_policy: InjectionPolicy,
                 boost_mode: bool,
                 ptr_flow_models: Optional[Dict] = None,
                 treechannels: int = 1):
        """Initialize NcclTreeFlowModel algorithm
        
        Args:
            com_type: Communication type
            id: Node ID
            layer_num: Layer number
            ring_topology: Ring topology
            data_size: Data size
            direction: Ring direction
            injection_policy: Injection policy
            boost_mode: Whether boost mode is enabled
            ptr_flow_models: Shared flow models
            treechannels: Number of tree channels
        """
        super().__init__(layer_num)
        
        # Timing
        self.start_time = time.time()
        self.end_time = time.time()
        
        # Basic properties
        self.comType = com_type
        self.id = id
        self.logicalTopology = ring_topology
        self.data_size = data_size
        self.nodes_in_ring = ring_topology.get_nodes_in_ring()
        self.parallel_reduce = 1
        self.toggle = False
        self.name = Algorithm.Name.Ring  # Note: C++ version uses Ring name
        self.enabled = True
        self.m_channels = treechannels
        
        # Synchronization
        self.judge_exit_flag = threading.Event()
        self.judge_exit_mutex = threading.Lock()
        self.judge_mutex = threading.Lock()
        
        # Packet counters
        self.send_packets = 0
        self.recv_packets = 0
        
        # Flow model data structures
        self._stream_count: Dict[int, int] = defaultdict(int)
        self.packets: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
        self.free_packets: Dict[Tuple[int, int], int] = defaultdict(int)
        self.indegree_mapping: Dict[int, int] = {}
        self.inprocessing_indegree: Dict[int, int] = {}
        self.zero_latency_packets: Dict[int, int] = {}
        self.non_zero_latency_packets: Dict[int, int] = {}
        self._flow_models: Dict[Tuple[int, int], Dict] = {}
        
        # Mock QPS system
        self.pQps = {
            'peer_qps': defaultdict(int),
            'peer_waiting_tasks': defaultdict(deque)
        }
        
        # State flags
        self.processed = False
        self.send_back = False
        self.NPU_to_MA = False
        
        if boost_mode:
            self.enabled = ring_topology.is_enabled()
        
        # Set transmission type
        if hasattr(ring_topology, 'dimension'):
            if ring_topology.dimension == ring_topology.Dimension.Local:
                self.transmition = "Fast"
            else:
                self.transmition = "Usual"
        else:
            self.transmition = "Usual"
        
        # Initialize flow models
        if ptr_flow_models:
            self._initialize_flow_models(ptr_flow_models)
        
        # Initialize channel maps
        for channel_id in range(self.m_channels):
            self.zero_latency_packets[channel_id] = 0
            self.non_zero_latency_packets[channel_id] = 0
        
        self._init_indegree_mapping()
        
        # Set final data size based on communication type
        if com_type == ComType.All_Reduce:
            self.final_data_size = data_size
        elif com_type == ComType.All_Gather:
            self.final_data_size = data_size * self.nodes_in_ring
        elif com_type == ComType.Reduce_Scatter:
            self.final_data_size = data_size // self.nodes_in_ring
        elif com_type == ComType.All_to_All:
            self.final_data_size = data_size
    
    def _initialize_flow_models(self, ptr_flow_models: Dict) -> None:
        """Initialize flow models from shared pointer
        
        Args:
            ptr_flow_models: Flow models dictionary
        """
        for f_key, f_value in ptr_flow_models.items():
            if f_value.get('dest') == self.id:
                channel_src_pair = (f_value['channel_id'], f_value['src'])
                self.free_packets[channel_src_pair] += 1
                self._flow_models[f_key] = f_value
                self.recv_packets += 1
            
            if f_value.get('src') == self.id:
                qp_key = (f_value['channel_id'], (f_value['src'], f_value['dest']))
                if qp_key not in self.pQps['peer_qps']:
                    self.pQps['peer_qps'][qp_key] = 1
                
                with self._g_flow_inCriticalSection:
                    self._stream_count[f_value['channel_id']] += 1
                
                self._flow_models[f_key] = f_value
                self.send_packets += 1
    
    def _init_indegree_mapping(self) -> None:
        """Initialize indegree mapping for flow dependencies"""
        for flow_key, flow_value in self._flow_models.items():
            if flow_value.get('src') != self.id:
                continue
            flow_id = flow_key[1]
            parent_flow_ids = flow_value.get('parent_flow_id', [])
            self.indegree_mapping[flow_id] = len(parent_flow_ids)
    
    def get_non_zero_latency_packets(self) -> int:
        """Get number of non-zero latency packets
        
        Returns:
            Number of non-zero latency packets
        """
        return (self.nodes_in_ring - 1) * self.parallel_reduce * 1
    
    def run(self, event: EventType, data: CallData) -> None:
        """Run the NcclTreeFlowModel algorithm
        
        Args:
            event: Event type
            data: Call data
        """
        # Extract channel_id and flow_id from data if available
        channel_id = getattr(data, 'channel_id', 0)
        flow_id = getattr(data, 'flow_id', 0)
        
        if event == EventType.General:
            self._ready(channel_id, flow_id)
            
        elif event == EventType.PacketReceived:
            # Handle packet received event
            flow_tag = getattr(data, 'flowTag', {})
            received_flow_id = flow_tag.get('current_flow_id', -1)
            channel_id = flow_tag.get('channel_id', 0)
            next_flow_list = flow_tag.get('tree_flow_list', [])
            
            # Update free packets
            sender_node = flow_tag.get('sender_node', 0)
            with self._g_flow_inCriticalSection:
                self.free_packets[(channel_id, sender_node)] -= 1
                
                # Check if all streams are finished
                all_finished = all(count == 0 for count in self._stream_count.values())
            
            if all_finished:
                self._ready(channel_id, -1)
                self._iteratable(channel_id)
                return
            
            # Process next flows
            for next_flow_id in next_flow_list:
                if next_flow_id in self.indegree_mapping:
                    with self._g_flow_inCriticalSection:
                        if self.indegree_mapping[next_flow_id] > 0:
                            self.indegree_mapping[next_flow_id] -= 1
                            if self.indegree_mapping[next_flow_id] == 0:
                                flow_model = self._flow_models.get((channel_id, next_flow_id))
                                if flow_model:
                                    self._insert_packets(channel_id, next_flow_id)
            
        elif event == EventType.StreamInit:
            # Initialize streams
            self.start_time = time.time()
            
            for i in range(self.parallel_reduce):
                self._init_recv_ready()
                
                for j in range(self.m_channels):
                    for flow_key, flow_model in self._flow_models.items():
                        if flow_model.get('src') != self.id:
                            continue
                        
                        parent_list = flow_model.get('parent_flow_id', [])
                        if len(parent_list) == 0 and flow_model['channel_id'] == j:
                            if flow_model.get('chunk_id', 0) == 0:
                                qp_key = (flow_model['channel_id'], 
                                         (flow_model['src'], flow_model['dest']))
                                self.pQps['peer_qps'][qp_key] = 0
                                self._insert_packets(j, flow_model['flow_id'])
                            else:
                                qp_key = (flow_model['channel_id'],
                                         (flow_model['src'], flow_model['dest']))
                                self.pQps['peer_waiting_tasks'][qp_key].append(
                                    flow_model['flow_id'])
        
        elif event == EventType.PacketSentFinshed:
            # Handle packet sent finished event
            flow_tag = getattr(data, 'flowTag', {})
            sent_flow_id = flow_tag.get('current_flow_id', -1)
            channel_id = flow_tag.get('channel_id', 0)
            
            self._reduce(channel_id, sent_flow_id)
            
            # Update QPS and handle waiting tasks
            sender_node = flow_tag.get('sender_node', 0)
            receiver_node = flow_tag.get('receiver_node', 0)
            qp_key = (channel_id, (sender_node, receiver_node))
            
            with self._g_flow_inCriticalSection:
                self.pQps['peer_qps'][qp_key] = 1
                
                if self.pQps['peer_waiting_tasks'][qp_key]:
                    cur_flow_id = self.pQps['peer_waiting_tasks'][qp_key].popleft()
                    self.pQps['peer_qps'][qp_key] = 0
                    self._insert_packets(channel_id, cur_flow_id)
            
            self._iteratable(channel_id)
    
    def _init_recv_ready(self) -> bool:
        """Initialize receive ready flows
        
        Returns:
            True if successful
        """
        recv_ready_flows: Dict[Tuple[int, List], List[int]] = defaultdict(list)
        
        for flow_key, flow_model in self._flow_models.items():
            if flow_model.get('src') != self.id:
                continue
            if flow_model.get('chunk_id', 0) != 0:
                continue
            if not flow_model.get('parent_flow_id', []):
                continue
            
            key = (flow_model['channel_id'], tuple(flow_model.get('prev', [])))
            recv_ready_flows[key].append(flow_model['flow_id'])
        
        # Process receive ready flows
        for key, flow_ids in recv_ready_flows.items():
            for flow_id in flow_ids:
                self._recv_ready(key[0], flow_id)
        
        return True
    
    def _recv_ready(self, channel_id: int, flow_id: int) -> bool:
        """Setup receive for a flow
        
        Args:
            channel_id: Channel ID
            flow_id: Flow ID
            
        Returns:
            True if successful
        """
        flow_model = self._flow_models.get((channel_id, flow_id))
        if not flow_model:
            return False
        
        recv_prevs = flow_model.get('prev', [])
        
        # Simulate receive setup for each previous node
        for recv_prev in recv_prevs:
            # In real implementation, this would call front_end_sim_recv
            pass
        
        return True
    
    def _release_packets(self, channel_id: int, flow_id: int, message_size: int) -> None:
        """Release packets for transmission
        
        Args:
            channel_id: Channel ID
            flow_id: Flow ID
            message_size: Message size
        """
        # Create packet bundle and send
        if hasattr(self.stream, 'owner'):
            # This would create a PacketBundle in the real implementation
            pass
    
    def _process_stream_count(self, channel_id: int) -> None:
        """Process stream count for a channel
        
        Args:
            channel_id: Channel ID
        """
        with self._g_flow_inCriticalSection:
            if self._stream_count[channel_id] > 0:
                self._stream_count[channel_id] -= 1
            
            if (self._stream_count[channel_id] == 0 and 
                self.stream.state != StreamState.Dead):
                self.stream.changeState(StreamState.Zombie)
    
    def _reduce(self, channel_id: int, flow_id: int) -> None:
        """Reduce operation
        
        Args:
            channel_id: Channel ID
            flow_id: Flow ID
        """
        self._process_stream_count(channel_id)
        
        packet_key = (channel_id, flow_id)
        if packet_key in self.packets and self.packets[packet_key]:
            self.packets[packet_key].pop(0)
    
    def _iteratable(self, channel_id: int) -> bool:
        """Check if algorithm can continue iterating
        
        Args:
            channel_id: Channel ID
            
        Returns:
            True if can continue, False otherwise
        """
        with self._g_flow_inCriticalSection:
            all_channel_finished = all(count == 0 for count in self._stream_count.values())
            all_packets_freed = all(count == 0 for count in self.free_packets.values())
        
        if all_channel_finished and all_packets_freed:
            self.exit()
            return False
        
        return True
    
    def _insert_packets(self, channel_id: int, flow_id: int) -> None:
        """Insert packets for processing
        
        Args:
            channel_id: Channel ID
            flow_id: Flow ID
        """
        if not self.enabled:
            return
        
        flow_model = self._flow_models.get((channel_id, flow_id))
        if not flow_model:
            return
        
        if (self.zero_latency_packets.get(channel_id, 0) == 0 and 
            self.non_zero_latency_packets.get(channel_id, 0) == 0):
            self.zero_latency_packets[channel_id] = self.parallel_reduce * 1
            self.non_zero_latency_packets[channel_id] = self.get_non_zero_latency_packets()
            self.toggle = not self.toggle
        
        current_receiver = flow_model.get('dest', 0)
        current_sender = flow_model.get('prev', [0])[0] if flow_model.get('prev') else 0
        message_size = flow_model.get('flow_size', 0)
        
        if self.zero_latency_packets.get(channel_id, 0) > 0:
            # Create packet
            packet = {
                'queue_id': self.stream.current_queue_id if self.stream else 0,
                'sender_id': current_sender,
                'receiver_id': current_receiver,
                'msg_size': message_size,
                'channel_id': channel_id,
                'flow_id': flow_id,
                'sender': None
            }
            
            self.packets[(channel_id, flow_id)].append(packet)
            self.processed = False
            self.send_back = False
            self.NPU_to_MA = True
            self._release_packets(channel_id, flow_id, message_size)
            self.zero_latency_packets[channel_id] -= 1
            
        elif self.non_zero_latency_packets.get(channel_id, 0) > 0:
            # Create packet
            packet = {
                'queue_id': self.stream.current_queue_id if self.stream else 0,
                'sender_id': current_sender,
                'receiver_id': current_receiver,
                'msg_size': message_size,
                'channel_id': channel_id,
                'flow_id': flow_id,
                'sender': None
            }
            
            self.packets[(channel_id, flow_id)].append(packet)
            
            if (self.comType == ComType.Reduce_Scatter or
                (self.comType == ComType.All_Reduce and self.toggle)):
                self.processed = True
            else:
                self.processed = False
            
            if self.non_zero_latency_packets[channel_id] <= self.parallel_reduce * 1:
                self.send_back = False
            else:
                self.send_back = True
            
            self.NPU_to_MA = False
            self._release_packets(channel_id, flow_id, message_size)
            self.non_zero_latency_packets[channel_id] -= 1
        else:
            raise RuntimeError("should not inject nothing!")
    
    def _ready(self, channel_id: int, flow_id: int) -> bool:
        """Check if ready to send packets
        
        Args:
            channel_id: Channel ID
            flow_id: Flow ID
            
        Returns:
            True if ready, False otherwise
        """
        if (self.stream.state in [StreamState.Created, StreamState.Ready]):
            self.stream.changeState(StreamState.Executing)
        
        packet_key = (channel_id, flow_id)
        if (not self.enabled or 
            not self.packets.get(packet_key) or 
            self._stream_count.get(channel_id, 0) == 0):
            return False
        
        packet = self.packets[packet_key][0]
        flow_model = self._flow_models.get((channel_id, flow_id))
        
        if not flow_model:
            return False
        
        # Simulate network operations
        # In real implementation, this would call front_end_sim_send/recv
        
        return True
    
    def exit(self) -> None:
        """Exit the algorithm"""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"Communication Latency: {duration * 1000000:.0f} us")
        
        # Clear packet lists
        for packet_list in self.packets.values():
            packet_list.clear()
        
        # Call parent exit method
        super().exit() 