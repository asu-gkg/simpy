"""
Trigger system for HTSimPy

A trigger is activated when an event completes and can cause other actions.
For example, a flow completion can trigger the start of another flow.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .eventlist import EventList


# Special value indicating connection should start via trigger
TRIGGER_START = 0xffffffffffffffff


class TriggerTarget(ABC):
    """
    Base class for objects that can be triggered.
    
    Triggers call activate() on TriggerTargets to cause them to do something.
    """
    
    @abstractmethod
    def activate(self) -> None:
        """Activate this target."""
        pass


class Trigger(ABC):
    """
    Base class for triggers.
    
    A trigger can have multiple targets that it activates when fired.
    """
    
    def __init__(self, eventlist: 'EventList', trigger_id: int):
        """
        Initialize trigger.
        
        Args:
            eventlist: Event list for scheduling
            trigger_id: Unique trigger ID
        """
        self._eventlist = eventlist
        self._id = trigger_id
        self._targets: List[TriggerTarget] = []
        
    def add_target(self, target: TriggerTarget) -> None:
        """
        Add a target to be activated by this trigger.
        
        Args:
            target: TriggerTarget to add
        """
        self._targets.append(target)
        
    @abstractmethod
    def activate(self) -> None:
        """Activate this trigger."""
        pass
        
    def get_id(self) -> int:
        """Get trigger ID."""
        return self._id


class SingleShotTrigger(Trigger):
    """
    Single-shot trigger that activates all targets once.
    
    Will assert if activated more than once as most targets
    cannot be restarted.
    """
    
    def __init__(self, eventlist: 'EventList', trigger_id: int):
        """Initialize single-shot trigger."""
        super().__init__(eventlist, trigger_id)
        self._done = False
        
    def activate(self) -> None:
        """
        Activate all targets once.
        
        Raises:
            AssertionError: If already activated
        """
        assert not self._done, f"SingleShotTrigger {self._id} already fired"
        assert len(self._targets) > 0, f"SingleShotTrigger {self._id} has no targets"
        
        print(f"Trigger {self._id} fired, {len(self._targets)} targets")
        
        # Schedule all targets for activation
        for target in self._targets:
            try:
                if hasattr(self._eventlist, 'trigger_is_pending'):
                    self._eventlist.trigger_is_pending(target)
                else:
                    # Direct activation if eventlist doesn't support triggers
                    target.activate()
            except Exception as e:
                # Log error and attempt direct activation as fallback
                import sys
                print(f"Warning: Trigger activation failed for target {target}: {e}", file=sys.stderr)
                try:
                    if hasattr(target, 'activate'):
                        target.activate()
                except Exception:
                    # If direct activation also fails, continue with other targets
                    pass
                
        self._done = True


class MultiShotTrigger(Trigger):
    """
    Multi-shot trigger that activates targets sequentially.
    
    Each call to activate() triggers the next target in sequence.
    """
    
    def __init__(self, eventlist: 'EventList', trigger_id: int):
        """Initialize multi-shot trigger."""
        super().__init__(eventlist, trigger_id)
        self._next = 0
        
    def activate(self) -> None:
        """Activate the next target in sequence."""
        if self._next >= len(self._targets):
            print("No one left to activate")
            return
            
        print(f"Multishot Trigger {self._id} fired, target {self._next} of {len(self._targets)}")
        
        # Activate next target
        target = self._targets[self._next]
        try:
            if hasattr(self._eventlist, 'trigger_is_pending'):
                self._eventlist.trigger_is_pending(target)
            else:
                target.activate()
        except Exception as e:
            # Log error and attempt direct activation as fallback
            import sys
            print(f"Warning: Trigger activation failed for target {target}: {e}", file=sys.stderr)
            try:
                if hasattr(target, 'activate'):
                    target.activate()
            except Exception:
                # If direct activation also fails, continue
                pass
            
        self._next += 1


class BarrierTrigger(Trigger):
    """
    Barrier trigger that requires multiple activations before firing.
    
    Activates all targets only after being activated a specified
    number of times.
    """
    
    def __init__(self, eventlist: 'EventList', trigger_id: int, 
                 activations_needed: int):
        """
        Initialize barrier trigger.
        
        Args:
            eventlist: Event list
            trigger_id: Trigger ID
            activations_needed: Number of activations required
        """
        super().__init__(eventlist, trigger_id)
        self._activations_remaining = activations_needed
        
    def activate(self) -> None:
        """
        Decrement activation count and fire if ready.
        
        Raises:
            AssertionError: If no activations remaining
        """
        assert self._activations_remaining > 0, \
            f"BarrierTrigger {self._id} activated too many times"
        assert len(self._targets) > 0, \
            f"BarrierTrigger {self._id} has no targets"
            
        self._activations_remaining -= 1
        
        if self._activations_remaining > 0:
            print(f"Trigger {self._id} activated, activations remaining: "
                  f"{self._activations_remaining}")
            return
            
        # All activations received - fire!
        print(f"Trigger {self._id} fired, {len(self._targets)} targets")
        
        for target in self._targets:
            try:
                if hasattr(self._eventlist, 'trigger_is_pending'):
                    self._eventlist.trigger_is_pending(target)
                else:
                    target.activate()
            except Exception as e:
                # Log error and attempt direct activation as fallback
                import sys
                print(f"Warning: Trigger activation failed for target {target}: {e}", file=sys.stderr)
                try:
                    if hasattr(target, 'activate'):
                        target.activate()
                except Exception:
                    # If direct activation also fails, continue with other targets
                    pass


class FlowTriggerTarget(TriggerTarget):
    """
    Trigger target that starts a flow when activated.
    """
    
    def __init__(self, flow_starter_fn):
        """
        Initialize flow trigger target.
        
        Args:
            flow_starter_fn: Function to call to start the flow
        """
        self._flow_starter_fn = flow_starter_fn
        
    def activate(self) -> None:
        """Start the flow."""
        self._flow_starter_fn()