# Mock NCCL communicator - corresponds to MockNcclChannel.h in SimAI

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from enum import Enum
from .common import ComType as AstraSimComType, Tick, ParallelStrategy

if TYPE_CHECKING:
    from .sys import Sys
    from .mock_nccl_group import MockNcclGroup


class State(Enum):
    """State enumeration for flow models"""
    Forward_Pass = "Forward_Pass"
    Weight_Gradient = "Weight_Gradient"
    Input_Gradient = "Input_Gradient"


class ComType(Enum):
    """Communication type enumeration matching MockNccl::ComType"""
    None_ = "None"
    Reduce_Scatter = "Reduce_Scatter"
    All_Gather = "All_Gather"
    All_Reduce = "All_Reduce"
    All_to_All = "All_to_All"
    All_Reduce_All_to_All = "All_Reduce_All_to_All"


class SingleFlow:
    """Single flow information for NCCL flow models
    
    Corresponds to MockNccl::SingleFlow struct
    """
    
    def __init__(self, flow_id: int = 0, src: int = 0, dest: int = 0, 
                 flow_size: int = 0, prev: Optional[List[int]] = None,
                 parent_flow_id: Optional[List[int]] = None,
                 child_flow_id: Optional[List[int]] = None,
                 channel_id: int = 0, chunk_id: int = 0, chunk_count: int = 0,
                 conn_type: str = ""):
        """Initialize single flow
        
        Args:
            flow_id: Unique flow identifier
            src: Source node ID
            dest: Destination node ID
            flow_size: Size of flow data
            prev: Previous flow dependencies
            parent_flow_id: Parent flow IDs
            child_flow_id: Child flow IDs
            channel_id: Channel identifier
            chunk_id: Chunk identifier
            chunk_count: Total chunk count
            conn_type: Connection type
        """
        self.flow_id = flow_id
        self.src = src
        self.dest = dest
        self.flow_size = flow_size
        self.prev = prev if prev is not None else []
        self.parent_flow_id = parent_flow_id if parent_flow_id is not None else []
        self.child_flow_id = child_flow_id if child_flow_id is not None else []
        self.channel_id = channel_id
        self.chunk_id = chunk_id
        self.chunk_count = chunk_count
        self.conn_type = conn_type


class ncclTree:
    """NCCL tree structure
    
    Corresponds to MockNccl::ncclTree struct
    """
    
    def __init__(self, depth: int = 0, rank: int = 0, up: int = -1, 
                 down: Optional[List[int]] = None):
        """Initialize NCCL tree
        
        Args:
            depth: Tree depth
            rank: Node rank
            up: Parent node rank
            down: Child node ranks
        """
        self.depth = depth
        self.rank = rank
        self.up = up
        self.down = down if down is not None else []


class ncclChannelNode:
    """NCCL channel node structure
    
    Corresponds to MockNccl::ncclChannelNode struct
    """
    
    def __init__(self, depth: int = 0, rank: int = 0, 
                 up: Optional['ncclChannelNode'] = None,
                 down: Optional[List['ncclChannelNode']] = None):
        """Initialize NCCL channel node
        
        Args:
            depth: Node depth in tree
            rank: Node rank
            up: Parent channel node
            down: Child channel nodes
        """
        self.depth = depth
        self.rank = rank
        self.up = up
        self.down = down if down is not None else []


class ncclInfo:
    """NCCL information structure for algorithms"""
    
    def __init__(self):
        """Initialize NCCL info"""
        self.collective_type: ComType = ComType.None_
        self.data_size = 0
        self.num_participants = 0
        self.participant_list: List[int] = []
        self.root_node = 0
        self.algorithm_name = ""
        self.expected_latency: Tick = 0
        self.bandwidth_requirement = 0.0
        self.protocol = ""
        self.algorithm = ""


# Type aliases for channel structures
TreeChannels = Dict[int, Dict[int, List[ncclTree]]]
NVLStreechannels = Dict[int, Dict[int, List[ncclChannelNode]]]


class MockNcclComm:
    """Mock NCCL communicator for simulation
    
    Corresponds to MockNccl::MockNcclComm class
    """
    
    def __init__(self, rank: int, group_type: ParallelStrategy, 
                 global_group: 'MockNcclGroup'):
        """Initialize mock NCCL communicator
        
        Args:
            rank: Node rank in the communicator
            group_type: Type of parallelism group
            global_group: Reference to global NCCL group
        """
        self.rank = rank
        self.type = group_type
        self.GlobalGroup = global_group
        
        # Channel structures
        self.ringchannels: Dict[int, Dict[int, List[int]]] = {}
        self.treechannels: TreeChannels = {}
        self.nvlschannels: TreeChannels = {}
        self.nvlstreechannels: NVLStreechannels = {}
        
        # Initialize channel structures
        self._initialize_channels()
    
    def _initialize_channels(self) -> None:
        """Initialize communication channels"""
        # Initialize ring channels
        self.ringchannels = {}
        
        # Initialize tree channels
        self.treechannels = {}
        
        # Initialize NVLS channels
        self.nvlschannels = {}
        
        # Initialize NVLS tree channels
        self.nvlstreechannels = {}
    
    def get_rings(self) -> Dict[int, Dict[int, List[int]]]:
        """Get ring channel topology
        
        Returns:
            Ring channel mapping
        """
        return self.ringchannels
    
    def get_treechannels(self) -> TreeChannels:
        """Get tree channel topology
        
        Returns:
            Tree channel mapping
        """
        return self.treechannels
    
    def get_nvls_channels(self) -> TreeChannels:
        """Get NVLS channel topology
        
        Returns:
            NVLS channel mapping
        """
        return self.nvlschannels
    
    def get_nvls_tree_channels(self) -> NVLStreechannels:
        """Get NVLS tree channel topology
        
        Returns:
            NVLS tree channel mapping
        """
        return self.nvlstreechannels
    
    def get_flow_model(self, data_size: int, collective_type: AstraSimComType,
                      layer_num: int, loop_state: State) -> Any:
        """Get flow model for collective operation
        
        Args:
            data_size: Size of data for collective
            collective_type: Type of collective operation
            layer_num: Layer number
            loop_state: Current loop state
            
        Returns:
            Flow model object
        """
        # Convert AstraSim ComType to MockNccl ComType
        mock_collective_type = self._convert_collective_type(collective_type)
        
        # Generate flow model based on parameters
        flow_model = {
            'data_size': data_size,
            'collective_type': mock_collective_type,
            'layer_num': layer_num,
            'loop_state': loop_state,
            'flows': [],
            'algorithm': self._select_algorithm(mock_collective_type, data_size),
            'estimated_time': self._estimate_time(mock_collective_type, data_size)
        }
        
        return flow_model
    
    def get_algo_proto_info(self, data_size: int, 
                           collective_type: AstraSimComType) -> ncclInfo:
        """Get algorithm and protocol information
        
        Args:
            data_size: Size of data for collective
            collective_type: Type of collective operation
            
        Returns:
            NCCL information structure
        """
        info = ncclInfo()
        info.collective_type = self._convert_collective_type(collective_type)
        info.data_size = data_size
        
        # Set algorithm and protocol based on collective type and data size
        if info.collective_type == ComType.All_Reduce:
            if data_size < 1024:
                info.algorithm = "Tree"
                info.protocol = "Simple"
            else:
                info.algorithm = "Ring"
                info.protocol = "LL"
        elif info.collective_type == ComType.All_Gather:
            info.algorithm = "Ring"
            info.protocol = "Simple"
        elif info.collective_type == ComType.Reduce_Scatter:
            info.algorithm = "Ring" 
            info.protocol = "Simple"
        elif info.collective_type == ComType.All_to_All:
            info.algorithm = "Direct"
            info.protocol = "Simple"
        else:
            info.algorithm = "Default"
            info.protocol = "Simple"
        
        info.algorithm_name = f"{info.algorithm}_{info.protocol}"
        
        return info
    
    def _convert_collective_type(self, astra_type: AstraSimComType) -> ComType:
        """Convert AstraSim ComType to MockNccl ComType
        
        Args:
            astra_type: AstraSim collective type
            
        Returns:
            MockNccl collective type
        """
        conversion_map = {
            AstraSimComType.All_Reduce: ComType.All_Reduce,
            AstraSimComType.All_Gather: ComType.All_Gather,
            AstraSimComType.Reduce_Scatter: ComType.Reduce_Scatter,
            AstraSimComType.All_to_All: ComType.All_to_All,
            AstraSimComType.None_: ComType.None_
        }
        
        return conversion_map.get(astra_type, ComType.None_)
    
    def _select_algorithm(self, collective_type: ComType, data_size: int) -> str:
        """Select appropriate algorithm for collective operation
        
        Args:
            collective_type: Type of collective
            data_size: Size of data
            
        Returns:
            Algorithm name
        """
        if collective_type == ComType.All_Reduce:
            return "Ring" if data_size >= 1024 else "Tree"
        elif collective_type == ComType.All_Gather:
            return "Ring"
        elif collective_type == ComType.Reduce_Scatter:
            return "Ring"
        elif collective_type == ComType.All_to_All:
            return "Direct"
        else:
            return "Default"
    
    def _estimate_time(self, collective_type: ComType, data_size: int) -> Tick:
        """Estimate execution time for collective operation
        
        Args:
            collective_type: Type of collective
            data_size: Size of data
            
        Returns:
            Estimated time in ticks
        """
        # Simplified time estimation
        base_latency = 100
        bandwidth_factor = 0.1
        
        if collective_type == ComType.All_Reduce:
            return int(base_latency + bandwidth_factor * data_size * 2)
        elif collective_type == ComType.All_Gather:
            return int(base_latency + bandwidth_factor * data_size)
        elif collective_type == ComType.Reduce_Scatter:
            return int(base_latency + bandwidth_factor * data_size)
        elif collective_type == ComType.All_to_All:
            return int(base_latency + bandwidth_factor * data_size * 4)
        else:
            return base_latency 