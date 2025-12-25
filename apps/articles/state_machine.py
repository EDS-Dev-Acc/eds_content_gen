"""
Article Processing State Machine.

Provides a robust state machine for managing article processing workflow:
- Clear state transitions with validation
- Hook system for before/after state changes
- Error handling with automatic retry support
- State history tracking
- Concurrent processing safety

States:
    collected → extracting → extracted → translating → translated → scoring → scored → completed
                    ↓             ↓            ↓             ↓          ↓
                  failed       failed       failed        failed      failed

Usage:
    machine = ArticleStateMachine(article)
    machine.transition_to('extracting')
    # ... do extraction work ...
    machine.transition_to('extracted')
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from functools import wraps

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ArticleState(Enum):
    """Valid states for article processing."""
    COLLECTED = 'collected'
    EXTRACTING = 'extracting'
    EXTRACTED = 'extracted'
    TRANSLATING = 'translating'
    TRANSLATED = 'translated'
    SCORING = 'scoring'
    SCORED = 'scored'
    COMPLETED = 'completed'
    FAILED = 'failed'
    
    @classmethod
    def from_string(cls, value: str) -> 'ArticleState':
        """Convert string to ArticleState."""
        for state in cls:
            if state.value == value:
                return state
        raise ValueError(f"Unknown state: {value}")
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions)."""
        return self in (ArticleState.COMPLETED, ArticleState.FAILED)
    
    @property
    def is_processing(self) -> bool:
        """Check if this is an active processing state."""
        return self in (
            ArticleState.EXTRACTING,
            ArticleState.TRANSLATING,
            ArticleState.SCORING,
        )


# Define valid state transitions
VALID_TRANSITIONS: Dict[ArticleState, Set[ArticleState]] = {
    ArticleState.COLLECTED: {ArticleState.EXTRACTING, ArticleState.FAILED},
    ArticleState.EXTRACTING: {ArticleState.EXTRACTED, ArticleState.FAILED},
    ArticleState.EXTRACTED: {ArticleState.TRANSLATING, ArticleState.SCORING, ArticleState.FAILED},
    ArticleState.TRANSLATING: {ArticleState.TRANSLATED, ArticleState.FAILED},
    ArticleState.TRANSLATED: {ArticleState.SCORING, ArticleState.FAILED},
    ArticleState.SCORING: {ArticleState.SCORED, ArticleState.FAILED},
    ArticleState.SCORED: {ArticleState.COMPLETED, ArticleState.FAILED},
    ArticleState.COMPLETED: set(),  # Terminal state
    ArticleState.FAILED: {ArticleState.COLLECTED},  # Can retry from failed
}


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: ArticleState
    to_state: ArticleState
    timestamp: datetime
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionContext:
    """Context passed to transition hooks."""
    article: Any  # Article model instance
    from_state: ArticleState
    to_state: ArticleState
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def set(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)


# Type for hook functions
HookFunction = Callable[[TransitionContext], None]


class TransitionError(Exception):
    """Raised when a state transition is invalid."""
    pass


class ArticleStateMachine:
    """
    State machine for managing article processing workflow.
    
    Features:
    - Validates state transitions
    - Runs before/after hooks
    - Tracks transition history
    - Handles errors gracefully
    - Thread-safe with database transactions
    """
    
    # Class-level hooks (shared across all instances)
    _global_before_hooks: Dict[Tuple[ArticleState, ArticleState], List[HookFunction]] = {}
    _global_after_hooks: Dict[Tuple[ArticleState, ArticleState], List[HookFunction]] = {}
    _global_on_enter_hooks: Dict[ArticleState, List[HookFunction]] = {}
    _global_on_exit_hooks: Dict[ArticleState, List[HookFunction]] = {}
    
    def __init__(self, article, max_retries: int = 3):
        """
        Initialize state machine for an article.
        
        Args:
            article: Article model instance
            max_retries: Maximum retry attempts for failed processing
        """
        self.article = article
        self.max_retries = max_retries
        self._history: List[StateTransition] = []
        
        # Instance-level hooks
        self._before_hooks: Dict[Tuple[ArticleState, ArticleState], List[HookFunction]] = {}
        self._after_hooks: Dict[Tuple[ArticleState, ArticleState], List[HookFunction]] = {}
    
    @property
    def current_state(self) -> ArticleState:
        """Get current state from article."""
        return ArticleState.from_string(self.article.processing_status)
    
    @property
    def history(self) -> List[StateTransition]:
        """Get transition history."""
        return self._history.copy()
    
    @property
    def retry_count(self) -> int:
        """Get number of times processing has been retried."""
        metadata = self.article.metadata or {}
        return metadata.get('retry_count', 0)
    
    def can_transition_to(self, target: ArticleState) -> bool:
        """Check if transition to target state is valid."""
        current = self.current_state
        valid_targets = VALID_TRANSITIONS.get(current, set())
        return target in valid_targets
    
    def get_valid_transitions(self) -> Set[ArticleState]:
        """Get all valid next states from current state."""
        return VALID_TRANSITIONS.get(self.current_state, set()).copy()
    
    def transition_to(
        self,
        target: ArticleState | str,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> bool:
        """
        Transition article to a new state.
        
        Args:
            target: Target state (ArticleState or string)
            error: Error message if transitioning to FAILED
            metadata: Additional metadata to store
            force: Force transition even if invalid (use with caution)
            
        Returns:
            True if transition succeeded
            
        Raises:
            TransitionError: If transition is invalid and force=False
        """
        # Convert string to enum if needed
        if isinstance(target, str):
            target = ArticleState.from_string(target)
        
        current = self.current_state
        
        # Check if transition is valid
        if not force and not self.can_transition_to(target):
            raise TransitionError(
                f"Invalid transition from {current.value} to {target.value}. "
                f"Valid targets: {[s.value for s in self.get_valid_transitions()]}"
            )
        
        # Create transition context
        context = TransitionContext(
            article=self.article,
            from_state=current,
            to_state=target,
            metadata=metadata or {},
        )
        
        try:
            with transaction.atomic():
                # Run before hooks
                self._run_hooks('before', current, target, context)
                self._run_on_exit_hooks(current, context)
                
                # Update article state
                self.article.processing_status = target.value
                
                # Handle error case
                if target == ArticleState.FAILED and error:
                    self.article.processing_error = error
                    # Increment retry count
                    if self.article.metadata is None:
                        self.article.metadata = {}
                    self.article.metadata['retry_count'] = self.retry_count + 1
                    self.article.metadata['last_error'] = error
                    self.article.metadata['last_error_at'] = timezone.now().isoformat()
                
                # Clear error on successful transition
                if target != ArticleState.FAILED:
                    self.article.processing_error = ''
                
                # Store transition metadata
                if metadata:
                    if self.article.metadata is None:
                        self.article.metadata = {}
                    self.article.metadata['last_transition'] = {
                        'from': current.value,
                        'to': target.value,
                        'at': timezone.now().isoformat(),
                        **metadata,
                    }
                
                # Save article
                self.article.save()
                
                # Run after hooks
                self._run_on_enter_hooks(target, context)
                self._run_hooks('after', current, target, context)
                
                # Record in history
                self._history.append(StateTransition(
                    from_state=current,
                    to_state=target,
                    timestamp=timezone.now(),
                    success=True,
                    metadata=metadata or {},
                ))
                
                logger.info(
                    f"Article {self.article.id} transitioned: "
                    f"{current.value} → {target.value}"
                )
                
                return True
                
        except Exception as e:
            # Record failed transition
            self._history.append(StateTransition(
                from_state=current,
                to_state=target,
                timestamp=timezone.now(),
                success=False,
                error=str(e),
                metadata=metadata or {},
            ))
            
            logger.error(
                f"Article {self.article.id} transition failed: "
                f"{current.value} → {target.value}: {e}"
            )
            raise
    
    def fail(self, error: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Transition to FAILED state.
        
        Args:
            error: Error message
            metadata: Additional metadata
        """
        self.transition_to(ArticleState.FAILED, error=error, metadata=metadata)
    
    def retry(self) -> bool:
        """
        Retry processing from FAILED state.
        
        Returns:
            True if retry was initiated, False if max retries exceeded
        """
        if self.current_state != ArticleState.FAILED:
            raise TransitionError("Can only retry from FAILED state")
        
        if self.retry_count >= self.max_retries:
            logger.warning(
                f"Article {self.article.id} exceeded max retries ({self.max_retries})"
            )
            return False
        
        self.transition_to(ArticleState.COLLECTED, metadata={'retry': True})
        return True
    
    def reset(self):
        """Reset article to COLLECTED state (for reprocessing)."""
        with transaction.atomic():
            self.article.processing_status = ArticleState.COLLECTED.value
            self.article.processing_error = ''
            if self.article.metadata is None:
                self.article.metadata = {}
            self.article.metadata['retry_count'] = 0
            self.article.metadata['reset_at'] = timezone.now().isoformat()
            self.article.save()
        
        self._history.clear()
        logger.info(f"Article {self.article.id} reset to COLLECTED state")
    
    # Hook registration methods
    def before(
        self,
        from_state: ArticleState,
        to_state: ArticleState,
        hook: HookFunction,
    ):
        """Register a before-transition hook for this instance."""
        key = (from_state, to_state)
        if key not in self._before_hooks:
            self._before_hooks[key] = []
        self._before_hooks[key].append(hook)
    
    def after(
        self,
        from_state: ArticleState,
        to_state: ArticleState,
        hook: HookFunction,
    ):
        """Register an after-transition hook for this instance."""
        key = (from_state, to_state)
        if key not in self._after_hooks:
            self._after_hooks[key] = []
        self._after_hooks[key].append(hook)
    
    @classmethod
    def register_before_hook(
        cls,
        from_state: ArticleState,
        to_state: ArticleState,
        hook: HookFunction,
    ):
        """Register a global before-transition hook."""
        key = (from_state, to_state)
        if key not in cls._global_before_hooks:
            cls._global_before_hooks[key] = []
        cls._global_before_hooks[key].append(hook)
    
    @classmethod
    def register_after_hook(
        cls,
        from_state: ArticleState,
        to_state: ArticleState,
        hook: HookFunction,
    ):
        """Register a global after-transition hook."""
        key = (from_state, to_state)
        if key not in cls._global_after_hooks:
            cls._global_after_hooks[key] = []
        cls._global_after_hooks[key].append(hook)
    
    @classmethod
    def register_on_enter(cls, state: ArticleState, hook: HookFunction):
        """Register a hook to run when entering a state."""
        if state not in cls._global_on_enter_hooks:
            cls._global_on_enter_hooks[state] = []
        cls._global_on_enter_hooks[state].append(hook)
    
    @classmethod
    def register_on_exit(cls, state: ArticleState, hook: HookFunction):
        """Register a hook to run when exiting a state."""
        if state not in cls._global_on_exit_hooks:
            cls._global_on_exit_hooks[state] = []
        cls._global_on_exit_hooks[state].append(hook)
    
    # Internal hook execution
    def _run_hooks(
        self,
        phase: str,
        from_state: ArticleState,
        to_state: ArticleState,
        context: TransitionContext,
    ):
        """Run hooks for a transition."""
        key = (from_state, to_state)
        
        # Get hooks to run
        if phase == 'before':
            global_hooks = self._global_before_hooks.get(key, [])
            instance_hooks = self._before_hooks.get(key, [])
        else:
            global_hooks = self._global_after_hooks.get(key, [])
            instance_hooks = self._after_hooks.get(key, [])
        
        # Run all hooks
        for hook in global_hooks + instance_hooks:
            try:
                hook(context)
            except Exception as e:
                logger.error(f"Hook error during {phase} {from_state}→{to_state}: {e}")
                if phase == 'before':
                    raise  # Before hooks can abort transition
    
    def _run_on_enter_hooks(self, state: ArticleState, context: TransitionContext):
        """Run on-enter hooks for a state."""
        for hook in self._global_on_enter_hooks.get(state, []):
            try:
                hook(context)
            except Exception as e:
                logger.error(f"On-enter hook error for {state}: {e}")
    
    def _run_on_exit_hooks(self, state: ArticleState, context: TransitionContext):
        """Run on-exit hooks for a state."""
        for hook in self._global_on_exit_hooks.get(state, []):
            try:
                hook(context)
            except Exception as e:
                logger.error(f"On-exit hook error for {state}: {e}")


def with_state_machine(func: Callable) -> Callable:
    """
    Decorator to wrap a processing function with state machine transitions.
    
    The decorated function should accept (article, machine, *args, **kwargs).
    It will automatically transition states before and after the function.
    
    Usage:
        @with_state_machine
        def extract_article(article, machine):
            machine.transition_to('extracting')
            # ... do extraction ...
            machine.transition_to('extracted')
    """
    @wraps(func)
    def wrapper(article, *args, **kwargs):
        machine = ArticleStateMachine(article)
        try:
            return func(article, machine, *args, **kwargs)
        except Exception as e:
            machine.fail(str(e))
            raise
    return wrapper


class ProcessingPipeline:
    """
    Pipeline for processing articles through multiple stages.
    
    Usage:
        pipeline = ProcessingPipeline()
        pipeline.add_stage('extract', extract_func, ArticleState.EXTRACTING, ArticleState.EXTRACTED)
        pipeline.add_stage('translate', translate_func, ArticleState.TRANSLATING, ArticleState.TRANSLATED)
        pipeline.add_stage('score', score_func, ArticleState.SCORING, ArticleState.SCORED)
        
        pipeline.process(article)
    """
    
    @dataclass
    class Stage:
        name: str
        func: Callable
        start_state: ArticleState
        end_state: ArticleState
        skip_if: Optional[Callable] = None
    
    def __init__(self):
        self.stages: List[ProcessingPipeline.Stage] = []
    
    def add_stage(
        self,
        name: str,
        func: Callable,
        start_state: ArticleState,
        end_state: ArticleState,
        skip_if: Optional[Callable] = None,
    ):
        """
        Add a processing stage.
        
        Args:
            name: Stage name for logging
            func: Function to run (receives article as argument)
            start_state: State to transition to before running
            end_state: State to transition to after success
            skip_if: Optional function to check if stage should be skipped
        """
        self.stages.append(self.Stage(
            name=name,
            func=func,
            start_state=start_state,
            end_state=end_state,
            skip_if=skip_if,
        ))
    
    def process(self, article, start_from: Optional[ArticleState] = None) -> bool:
        """
        Process article through all stages.
        
        Args:
            article: Article to process
            start_from: Optionally start from a specific stage
            
        Returns:
            True if all stages completed successfully
        """
        machine = ArticleStateMachine(article)
        
        # Find starting point
        start_index = 0
        if start_from:
            for i, stage in enumerate(self.stages):
                if stage.start_state == start_from:
                    start_index = i
                    break
        
        # Run stages
        for stage in self.stages[start_index:]:
            # Check skip condition
            if stage.skip_if and stage.skip_if(article):
                logger.info(f"Skipping stage '{stage.name}' for article {article.id}")
                continue
            
            try:
                # Transition to start state
                if machine.can_transition_to(stage.start_state):
                    machine.transition_to(stage.start_state)
                
                # Run stage function
                logger.info(f"Running stage '{stage.name}' for article {article.id}")
                stage.func(article)
                
                # Transition to end state
                machine.transition_to(stage.end_state)
                
            except Exception as e:
                logger.error(f"Stage '{stage.name}' failed for article {article.id}: {e}")
                machine.fail(f"{stage.name}: {e}")
                return False
        
        # Final transition to completed
        if machine.can_transition_to(ArticleState.COMPLETED):
            machine.transition_to(ArticleState.COMPLETED)
        
        return True
    
    def get_current_stage(self, article) -> Optional[str]:
        """Get the current stage name based on article state."""
        current = ArticleState.from_string(article.processing_status)
        
        for stage in self.stages:
            if current in (stage.start_state, stage.end_state):
                return stage.name
        
        return None
